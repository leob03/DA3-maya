"""Package paths used by DA3 Maya."""

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PACKAGE_ROOT / "scripts"
MODELS_DIR = PACKAGE_ROOT / "models"
DEPS_PUBLIC_DIR = PACKAGE_ROOT / "deps_public"
DEPS_DA3_DIR = PACKAGE_ROOT / "deps_da3"
DA3_REPO_DIR = PACKAGE_ROOT / "da3_repo"
INSTALL_LOG_DIR = PACKAGE_ROOT / "install_logs"
REQUIREMENTS_TXT = PACKAGE_ROOT / "requirements.txt"
REQUIREMENTS_MACOS_TXT = PACKAGE_ROOT / "requirements-macos.txt"
