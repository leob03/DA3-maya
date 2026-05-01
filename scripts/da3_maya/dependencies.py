"""Dependency management for the Maya DA3 package."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from .paths import DA3_REPO_DIR, DEPS_DA3_DIR, DEPS_PUBLIC_DIR, REQUIREMENTS_TXT


def prepend_dependency_paths() -> None:
    """Make vendored dependencies importable in the current Maya Python session."""
    for path in (DEPS_PUBLIC_DIR, DEPS_DA3_DIR, DA3_REPO_DIR):
        path_str = os.fspath(path)
        if path.exists() and path_str not in sys.path:
            sys.path.insert(0, path_str)


def check() -> tuple[bool, str]:
    """Return whether the required runtime imports are available."""
    prepend_dependency_paths()
    missing = []
    for module_name in ("torch", "numpy", "cv2", "safetensors", "depth_anything_3"):
        try:
            __import__(module_name)
        except Exception as exc:
            missing.append(f"{module_name}: {exc}")
    if missing:
        return False, "\n".join(missing)
    return True, "Dependencies are available."


def install() -> tuple[bool, str]:
    """Install DA3 and Python dependencies into this package directory."""
    try:
        if not DA3_REPO_DIR.exists():
            subprocess.check_call(
                [
                    "git",
                    "clone",
                    "--recursive",
                    "https://github.com/ByteDance-Seed/Depth-Anything-3.git",
                    os.fspath(DA3_REPO_DIR),
                ]
            )
        elif (DA3_REPO_DIR / ".git").exists():
            subprocess.check_call(["git", "-C", os.fspath(DA3_REPO_DIR), "submodule", "update", "--init", "--recursive"])

        DEPS_PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
        DEPS_DA3_DIR.mkdir(parents=True, exist_ok=True)

        subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"])
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                os.fspath(REQUIREMENTS_TXT),
                "--target",
                os.fspath(DEPS_PUBLIC_DIR),
            ]
        )

        if DEPS_DA3_DIR.exists():
            shutil.rmtree(DEPS_DA3_DIR)
        DEPS_DA3_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                os.fspath(DA3_REPO_DIR),
                "--target",
                os.fspath(DEPS_DA3_DIR),
            ]
        )
    except subprocess.CalledProcessError as exc:
        return False, f"Dependency install failed: {exc}"
    except Exception as exc:
        return False, f"Dependency install failed: {exc}"

    return check()
