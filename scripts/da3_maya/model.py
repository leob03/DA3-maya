"""DA3 model loading and inference utilities."""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path
from types import SimpleNamespace

from .dependencies import prepend_dependency_paths
from .paths import MODELS_DIR


MODEL_URLS = {
    "da3-small": "https://huggingface.co/depth-anything/DA3-SMALL/resolve/main/model.safetensors",
    "da3-base": "https://huggingface.co/depth-anything/DA3-BASE/resolve/main/model.safetensors",
    "da3-large": "https://huggingface.co/depth-anything/DA3-LARGE/resolve/main/model.safetensors",
    "da3-large-1.1": "https://huggingface.co/depth-anything/DA3-LARGE-1.1/resolve/main/model.safetensors",
    "da3-giant": "https://huggingface.co/depth-anything/DA3-GIANT/resolve/main/model.safetensors",
    "da3-giant-1.1": "https://huggingface.co/depth-anything/DA3-GIANT-1.1/resolve/main/model.safetensors",
    "da3metric-large": "https://huggingface.co/depth-anything/DA3METRIC-LARGE/resolve/main/model.safetensors",
    "da3mono-large": "https://huggingface.co/depth-anything/DA3MONO-LARGE/resolve/main/model.safetensors",
    "da3nested-giant-large": "https://huggingface.co/depth-anything/DA3NESTED-GIANT-LARGE/resolve/main/model.safetensors",
    "da3nested-giant-large-1.1": "https://huggingface.co/depth-anything/DA3NESTED-GIANT-LARGE-1.1/resolve/main/model.safetensors",
}

CONFIG_NAME_MAP = {
    "da3-large-1.1": "da3-large",
    "da3-giant-1.1": "da3-giant",
    "da3nested-giant-large-1.1": "da3nested-giant-large",
}

_MODEL = None
_MODEL_NAME = None


def get_torch_device():
    """Choose the best PyTorch device for Maya's current machine."""
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        return "mps"
    return "cpu"


def get_model_path(model_name: str, model_folder: str | None = None) -> Path:
    folder = Path(model_folder) if model_folder else MODELS_DIR
    return folder / f"{model_name}.safetensors"


def download_model(model_name: str, model_folder: str | None = None, progress=None) -> Path:
    if model_name not in MODEL_URLS:
        raise ValueError(f"Unknown DA3 model: {model_name}")
    path = get_model_path(model_name, model_folder)
    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    url = MODEL_URLS[model_name]
    tmp_path = path.with_suffix(path.suffix + ".part")

    with urllib.request.urlopen(url) as response:
        total = int(response.info().get("Content-Length", -1))
        done = 0
        with open(tmp_path, "wb") as fh:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                if progress and total > 0:
                    progress(done / total)

    tmp_path.replace(path)
    return path


def unload_model() -> None:
    global _MODEL, _MODEL_NAME
    old_model = _MODEL
    _MODEL = None
    _MODEL_NAME = None
    del old_model
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            try:
                torch.mps.empty_cache()
            except Exception:
                pass
    except Exception:
        pass


def load_model(model_name: str, model_folder: str | None = None):
    global _MODEL, _MODEL_NAME
    prepend_dependency_paths()

    if _MODEL is not None and _MODEL_NAME == model_name:
        return _MODEL

    unload_model()

    import torch
    from depth_anything_3.api import DepthAnything3
    from safetensors.torch import load_file

    path = get_model_path(model_name, model_folder)
    if not path.exists():
        raise FileNotFoundError(f"Model is not downloaded: {path}")

    config_name = CONFIG_NAME_MAP.get(model_name, model_name)
    da3_model = DepthAnything3(model_name=config_name)
    weights = load_file(os.fspath(path), device="cpu")
    da3_model.load_state_dict(weights, strict=False)
    device = get_torch_device()
    print(f"[DA3 Maya] Loading {model_name} on {device}")
    da3_model.to(device)
    da3_model.eval()

    _MODEL = da3_model
    _MODEL_NAME = model_name
    return _MODEL


def run_inference(
    image_paths: list[str],
    model_name: str,
    model_folder: str | None = None,
    process_res: int = 504,
    process_res_method: str = "upper_bound_resize",
    use_ray_pose: bool = False,
    ref_view_strategy: str = "saddle_balanced",
):
    if process_res % 14 != 0:
        raise ValueError("Process resolution must be a multiple of 14.")
    if not image_paths:
        raise ValueError("No images provided.")

    import torch

    da3_model = load_model(model_name, model_folder)
    with torch.no_grad():
        pred = da3_model.inference(
            image_paths,
            process_res=process_res,
            process_res_method=process_res_method,
            use_ray_pose=use_ray_pose,
            ref_view_strategy=ref_view_strategy,
        )
    return pred


def prediction_as_namespace(**kwargs):
    return SimpleNamespace(**kwargs)
