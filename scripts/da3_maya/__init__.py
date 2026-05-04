"""Maya entry points for DA3 Maya."""

from .ui import show, show_floating
from .startup import install_startup_ui as install_ui

__all__ = ["show", "show_floating", "install_ui"]
