"""Maya entry points for DA3 Maya."""

from .ui import show
from .startup import install_startup_ui as install_ui

__all__ = ["show", "install_ui"]
