"""Install DA3 Maya as a Maya module for the current user."""

from __future__ import annotations

import os
import platform
from pathlib import Path


def _module_dir() -> Path:
    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        return home / "Library" / "Preferences" / "Autodesk" / "maya" / "modules"
    if system == "Windows":
        return home / "Documents" / "maya" / "modules"
    return home / "maya" / "modules"


def install() -> Path:
    repo = Path(__file__).resolve().parent
    module_dir = _module_dir()
    module_dir.mkdir(parents=True, exist_ok=True)
    module_path = module_dir / "DA3Maya.mod"
    module_path.write_text(
        f"+ DA3Maya 0.1 {repo}\n"
        "PYTHONPATH +:= scripts\n",
        encoding="utf-8",
    )
    return module_path


if __name__ == "__main__":
    path = install()
    print(f"Installed DA3 Maya module: {path}")
    print("Restart Maya. A DA3 Maya menu and shelf button should appear.")
