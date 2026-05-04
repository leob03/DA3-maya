"""Maya startup hook for DA3 Maya module installs."""

from maya import cmds


def _install_da3_maya_ui():
    try:
        from da3_maya.startup import install_startup_ui

        install_startup_ui()
    except Exception as exc:
        print(f"[DA3 Maya] Startup UI install failed: {exc}")


cmds.evalDeferred(_install_da3_maya_ui)
