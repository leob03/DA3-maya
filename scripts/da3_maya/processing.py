"""DA3 prediction post-processing shared by the Maya importers."""

from __future__ import annotations

import os
from pathlib import Path


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG")


def collect_image_paths(input_folder: str, start_frame: int = 0, end_frame: int = -1, frame_stride: int = 1) -> list[str]:
    folder = Path(input_folder)
    if not folder.is_dir():
        raise NotADirectoryError(f"Input folder does not exist: {input_folder}")

    paths = sorted(str(p) for p in folder.iterdir() if p.suffix in IMAGE_EXTENSIONS)
    if not paths:
        raise FileNotFoundError(f"No images found in {input_folder}")

    start = max(0, int(start_frame))
    end = int(end_frame)
    if end >= 0:
        paths = paths[start : end + 1]
    else:
        paths = paths[start:]

    stride = max(1, int(frame_stride))
    return paths[::stride]


def _to_numpy(value):
    import numpy as np

    try:
        import torch

        if isinstance(value, torch.Tensor):
            return value.detach().cpu().float().numpy()
    except Exception:
        pass
    return np.asarray(value)


def unproject_depth_map_to_point_map(depth, extrinsics, intrinsics):
    import numpy as np

    depth = _to_numpy(depth)
    extrinsics = _to_numpy(extrinsics)
    intrinsics = _to_numpy(intrinsics)

    n_frames, height, width = depth.shape
    world_points = np.zeros((n_frames, height, width, 3), dtype=np.float32)
    u, v = np.meshgrid(np.arange(width), np.arange(height))
    pixels = np.stack([u, v, np.ones((height, width))], axis=-1).reshape(-1, 3)

    for i in range(n_frames):
        inv_k = np.linalg.inv(intrinsics[i])
        rays = (inv_k @ pixels.T).T
        depths = depth[i].reshape(-1)
        cam_points = rays * depths[:, None]
        cam_points_hom = np.hstack([cam_points, np.ones((len(depths), 1))])
        world_to_cam = np.vstack([extrinsics[i], [0, 0, 0, 1]])
        cam_to_world = np.linalg.inv(world_to_cam)
        world_hom = (cam_to_world @ cam_points_hom.T).T
        world_points[i] = (world_hom[:, :3] / world_hom[:, 3:4]).reshape(height, width, 3)

    return world_points


def apply_edge_filter(depth, conf, enabled=True):
    if not enabled:
        return conf

    import cv2
    import numpy as np

    conf = conf.copy()
    for i in range(len(depth)):
        dm = depth[i].astype(np.float32)
        gx = cv2.Sobel(dm, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(dm, cv2.CV_64F, 0, 1, ksize=3)
        mag = np.sqrt(gx**2 + gy**2)
        mn = np.nanmin(mag)
        mx = np.nanmax(mag)
        norm = (mag - mn) / (mx - mn) if mx > mn else np.zeros_like(mag)
        conf[i][norm >= (12.0 / 255.0)] = 0.0
    return conf


def prediction_to_dict(prediction, image_paths: list[str] | None = None, filter_edges: bool = True):
    images = _to_numpy(prediction.processed_images).astype("float32") / 255.0
    depth = _to_numpy(prediction.depth)
    conf = _to_numpy(prediction.conf)
    extrinsic = _to_numpy(prediction.extrinsics)
    intrinsic = _to_numpy(prediction.intrinsics)

    if extrinsic is None or intrinsic is None:
        raise ValueError("Prediction has no camera parameters; cannot create Maya scene geometry.")

    conf = apply_edge_filter(depth, conf, enabled=filter_edges)
    result = {
        "images": images,
        "depth": depth,
        "conf": conf,
        "extrinsic": extrinsic,
        "intrinsic": intrinsic,
        "world_points_from_depth": unproject_depth_map_to_point_map(depth, extrinsic, intrinsic),
    }
    if image_paths:
        result["image_paths"] = image_paths
    return result


def frame_number_from_path(image_path: str, fallback_index: int) -> int:
    return fallback_index + 1


def source_stem(input_folder: str) -> str:
    return os.path.basename(os.path.normpath(input_folder)) or "da3"
