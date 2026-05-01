"""Dependency management for the Maya DA3 package."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime

from .paths import DA3_REPO_DIR, DEPS_DA3_DIR, DEPS_PUBLIC_DIR, INSTALL_LOG_DIR, REQUIREMENTS_MACOS_TXT, REQUIREMENTS_TXT


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


def selected_requirements_file():
    """Return the requirements file for the current platform."""
    if platform.system() == "Darwin" and REQUIREMENTS_MACOS_TXT.exists():
        return REQUIREMENTS_MACOS_TXT
    return REQUIREMENTS_TXT


def install_log_path():
    """Return the log path used by the next dependency install."""
    INSTALL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return INSTALL_LOG_DIR / f"install_{stamp}.log"


def latest_install_log_path():
    if not INSTALL_LOG_DIR.exists():
        return None
    logs = sorted(INSTALL_LOG_DIR.glob("install_*.log"))
    return logs[-1] if logs else None


def _run_logged(cmd, log_file, cwd=None):
    log_file.write("\n$ " + " ".join(map(str, cmd)) + "\n")
    log_file.flush()
    proc = subprocess.Popen(
        [os.fspath(part) for part in cmd],
        cwd=os.fspath(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        log_file.write(line)
        log_file.flush()
        print(line, end="")
    ret = proc.wait()
    if ret != 0:
        raise subprocess.CalledProcessError(ret, cmd)


def install() -> tuple[bool, str]:
    """Install DA3 and Python dependencies into this package directory."""
    log_path = install_log_path()
    try:
        with open(log_path, "w", encoding="utf-8") as log_file:
            requirements_file = selected_requirements_file()
            log_file.write("DA3 Maya dependency install\n")
            log_file.write(f"Platform: {platform.platform()}\n")
            log_file.write(f"Python executable: {sys.executable}\n")
            log_file.write(f"Python version: {sys.version}\n")
            log_file.write(f"Requirements: {requirements_file}\n")
            log_file.write(f"deps_public: {DEPS_PUBLIC_DIR}\n")
            log_file.write(f"deps_da3: {DEPS_DA3_DIR}\n")
            log_file.write(f"da3_repo: {DA3_REPO_DIR}\n")
            log_file.flush()
            print(f"[DA3 Maya] Installing dependencies. Log: {log_path}")

            if not DA3_REPO_DIR.exists():
                _run_logged(
                    [
                        "git",
                        "clone",
                        "--recursive",
                        "https://github.com/ByteDance-Seed/Depth-Anything-3.git",
                        os.fspath(DA3_REPO_DIR),
                    ],
                    log_file,
                )
            elif (DA3_REPO_DIR / ".git").exists():
                _run_logged(["git", "-C", os.fspath(DA3_REPO_DIR), "submodule", "update", "--init", "--recursive"], log_file)

            DEPS_PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
            DEPS_DA3_DIR.mkdir(parents=True, exist_ok=True)

            _run_logged([sys.executable, "-m", "ensurepip", "--upgrade"], log_file)
            _run_logged(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    os.fspath(requirements_file),
                    "--target",
                    os.fspath(DEPS_PUBLIC_DIR),
                ],
                log_file,
            )

            if DEPS_DA3_DIR.exists():
                shutil.rmtree(DEPS_DA3_DIR)
            DEPS_DA3_DIR.mkdir(parents=True, exist_ok=True)
            _run_logged(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-deps",
                    os.fspath(DA3_REPO_DIR),
                    "--target",
                    os.fspath(DEPS_DA3_DIR),
                ],
                log_file,
            )
    except subprocess.CalledProcessError as exc:
        return False, f"Dependency install failed: {exc}\nLog: {log_path}"
    except Exception as exc:
        return False, f"Dependency install failed: {exc}\nLog: {log_path}"

    ok, message = check()
    if ok:
        return True, f"Dependencies are available.\nLog: {log_path}"
    return False, f"{message}\nLog: {log_path}"
