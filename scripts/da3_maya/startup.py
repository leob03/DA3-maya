"""Startup integration for DA3 Maya."""

from __future__ import annotations


MENU_NAME = "DA3MayaMenu"
SHELF_NAME = "DA3Maya"


def show_window(*_args):
    from .ui import show

    return show()


def install_menu():
    from maya import cmds, mel

    if cmds.menu(MENU_NAME, exists=True):
        return MENU_NAME

    main_window = mel.eval("$tmp = $gMainWindow")
    menu = cmds.menu(MENU_NAME, label="DA3 Maya", parent=main_window, tearOff=True)
    cmds.menuItem(label="Open DA3 Maya", parent=menu, command=lambda *_: show_window())
    cmds.menuItem(divider=True, parent=menu)
    cmds.menuItem(label="Unload DA3 Model", parent=menu, command=lambda *_: _unload_model())
    return menu


def install_shelf_button():
    from maya import cmds, mel

    shelf_parent = mel.eval("$tmp = $gShelfTopLevel")
    if not cmds.tabLayout(shelf_parent, exists=True):
        return None

    shelves = cmds.tabLayout(shelf_parent, query=True, childArray=True) or []
    if SHELF_NAME not in shelves:
        cmds.shelfLayout(SHELF_NAME, parent=shelf_parent)

    for child in cmds.shelfLayout(SHELF_NAME, query=True, childArray=True) or []:
        if cmds.shelfButton(child, query=True, annotation=True) == "Open DA3 Maya":
            cmds.shelfButton(
                child,
                edit=True,
                sourceType="python",
                command="import da3_maya; da3_maya.show()",
            )
            return child

    return cmds.shelfButton(
        parent=SHELF_NAME,
        label="DA3",
        annotation="Open DA3 Maya",
        image="commandButton.png",
        sourceType="python",
        command="import da3_maya; da3_maya.show()",
    )


def install_startup_ui(include_shelf: bool = False):
    menu = install_menu()
    shelf_button = install_shelf_button() if include_shelf else None
    return menu, shelf_button


def _unload_model():
    from .model import unload_model

    unload_model()
    print("[DA3 Maya] Model unloaded.")
