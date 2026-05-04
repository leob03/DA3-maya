"""Maya UI for DA3 generation/import."""

from __future__ import annotations

import os
import traceback

from .dependencies import check as check_dependencies
from .dependencies import install as install_dependencies
from .dependencies import latest_install_log_path
from .model import MODEL_URLS, download_model, get_model_path, run_inference, unload_model
from .processing import collect_image_paths, prediction_to_dict, source_stem
from .maya_scene import import_prediction
from .paths import MODELS_DIR


WINDOW = "DA3MayaWindow"
WORKSPACE_CONTROL = "DA3MayaWorkspaceControl"


def show():
    from maya import cmds

    if cmds.window(WINDOW, exists=True):
        cmds.deleteUI(WINDOW)
    if cmds.workspaceControl(WORKSPACE_CONTROL, exists=True):
        cmds.deleteUI(WORKSPACE_CONTROL)

    control = cmds.workspaceControl(
        WORKSPACE_CONTROL,
        label="DA3 Maya",
        retain=False,
        initialWidth=430,
        minimumWidth=360,
    )
    cmds.setParent(control)
    scroll = cmds.scrollLayout(childResizable=True, width=420)
    col = cmds.columnLayout(adjustableColumn=True, rowSpacing=8)

    cmds.frameLayout(label="Dependencies", collapsable=True, collapse=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
    status = cmds.text(label=_dependency_status_label(), align="left")
    cmds.button(label="Check Dependencies", command=lambda *_: _set_status_text(status, _dependency_status_label()))
    cmds.button(label="Install Dependencies", command=lambda *_: _install(status))
    cmds.button(label="Print Latest Install Log Path", command=lambda *_: _print_latest_install_log(status))
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(label="Model", collapsable=True, collapse=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
    model_menu = cmds.optionMenu(label="Model")
    for model_name in MODEL_URLS:
        cmds.menuItem(label=model_name)
    cmds.optionMenu(model_menu, edit=True, value="da3-large-1.1")
    model_folder = cmds.textFieldButtonGrp(
        label="Model Folder",
        text=os.fspath(MODELS_DIR),
        buttonLabel="Browse",
        buttonCommand=lambda *_: _browse_folder(model_folder),
    )
    cmds.button(label="Download Model", command=lambda *_: _download(model_menu, model_folder, status))
    cmds.button(label="Unload Model", command=lambda *_: _unload(status))
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(label="Input", collapsable=True, collapse=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
    input_folder = cmds.textFieldButtonGrp(label="Image Folder", buttonLabel="Browse", buttonCommand=lambda *_: _browse_folder(input_folder))
    output_folder = cmds.textFieldButtonGrp(label="Output Folder", buttonLabel="Browse", buttonCommand=lambda *_: _browse_folder(output_folder))
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    start_frame = cmds.intFieldGrp(label="Start", value1=0)
    end_frame = cmds.intFieldGrp(label="End", value1=-1)
    cmds.setParent("..")
    frame_stride = cmds.intSliderGrp(label="Frame Stride", field=True, minValue=1, maxValue=20, value=1)
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(label="DA3 Settings", collapsable=True, collapse=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
    process_res = cmds.intSliderGrp(label="Process Resolution", field=True, minValue=14, maxValue=1400, value=504, step=14)
    resize_menu = cmds.optionMenu(label="Resize Method")
    cmds.menuItem(label="upper_bound_resize")
    cmds.menuItem(label="lower_bound_resize")
    ref_menu = cmds.optionMenu(label="Reference View")
    for item in ("saddle_balanced", "first", "middle", "saddle_sim_range"):
        cmds.menuItem(label=item)
    use_ray_pose = cmds.checkBox(label="Use Ray-based Pose", value=False)
    filter_edges = cmds.checkBox(label="Filter Edges", value=True)
    min_conf = cmds.floatSliderGrp(label="Min Confidence", field=True, minValue=0.0, maxValue=10.0, value=0.5)
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(label="Import", collapsable=True, collapse=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
    import_cameras = cmds.checkBox(label="Import Cameras", value=True)
    animate_camera = cmds.checkBox(label="Animate Camera", value=True)
    keep_cameras = cmds.checkBox(label="Keep Individual Cameras", value=False)
    import_points = cmds.checkBox(label="Import Point Cloud", value=True)
    import_meshes = cmds.checkBox(label="Import Depth Meshes", value=False)
    per_frame_geo = cmds.checkBox(label="Per-frame Geometry", value=False)
    max_points = cmds.intFieldGrp(label="Max Points", value1=250000)
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.separator(height=12)
    cmds.button(
        label="Generate",
        height=36,
        command=lambda *_: _generate(
            model_menu=model_menu,
            model_folder=model_folder,
            input_folder=input_folder,
            output_folder=output_folder,
            start_frame=start_frame,
            end_frame=end_frame,
            frame_stride=frame_stride,
            process_res=process_res,
            resize_menu=resize_menu,
            ref_menu=ref_menu,
            use_ray_pose=use_ray_pose,
            filter_edges=filter_edges,
            min_conf=min_conf,
            import_cameras=import_cameras,
            animate_camera=animate_camera,
            keep_cameras=keep_cameras,
            import_points=import_points,
            import_meshes=import_meshes,
            per_frame_geo=per_frame_geo,
            max_points=max_points,
            status=status,
        ),
    )

    cmds.setParent("..")
    cmds.workspaceControl(WORKSPACE_CONTROL, edit=True, restore=True)
    return control


def _dependency_status_label() -> str:
    ok, message = check_dependencies()
    return "Dependencies: OK" if ok else f"Dependencies: missing\n{message}"


def _set_status_text(status_control, text: str) -> None:
    from maya import cmds

    cmds.text(status_control, edit=True, label=text)


def _browse_folder(control) -> None:
    from maya import cmds

    selected = cmds.fileDialog2(fileMode=3, dialogStyle=2)
    if selected:
        cmds.textFieldButtonGrp(control, edit=True, text=selected[0])


def _install(status_control) -> None:
    from maya import cmds

    _set_status_text(status_control, "Installing dependencies. A log file will be written under install_logs/ ...")
    cmds.refresh()
    ok, message = install_dependencies()
    _set_status_text(status_control, "Dependencies: OK\n" + message if ok else f"Dependencies install failed\n{message}")


def _print_latest_install_log(status_control) -> None:
    log_path = latest_install_log_path()
    message = f"Latest install log: {log_path}" if log_path else "No install log found yet."
    print(f"[DA3 Maya] {message}")
    _set_status_text(status_control, message)


def _download(model_menu, model_folder_control, status_control) -> None:
    from maya import cmds

    model_name = cmds.optionMenu(model_menu, query=True, value=True)
    model_folder = cmds.textFieldButtonGrp(model_folder_control, query=True, text=True)
    try:
        _set_status_text(status_control, f"Downloading {model_name}...")
        cmds.refresh()
        path = download_model(model_name, model_folder=model_folder)
        _set_status_text(status_control, f"Model ready: {path}")
    except Exception as exc:
        traceback.print_exc()
        _set_status_text(status_control, f"Download failed: {exc}")


def _unload(status_control) -> None:
    unload_model()
    _set_status_text(status_control, "Model unloaded.")


def _generate(**controls) -> None:
    from maya import cmds

    try:
        model_name = cmds.optionMenu(controls["model_menu"], query=True, value=True)
        model_folder = cmds.textFieldButtonGrp(controls["model_folder"], query=True, text=True)
        input_folder = cmds.textFieldButtonGrp(controls["input_folder"], query=True, text=True)
        output_folder = cmds.textFieldButtonGrp(controls["output_folder"], query=True, text=True) or None
        start_frame = cmds.intFieldGrp(controls["start_frame"], query=True, value1=True)
        end_frame = cmds.intFieldGrp(controls["end_frame"], query=True, value1=True)
        frame_stride = cmds.intSliderGrp(controls["frame_stride"], query=True, value=True)
        process_res = cmds.intSliderGrp(controls["process_res"], query=True, value=True)
        resize_method = cmds.optionMenu(controls["resize_menu"], query=True, value=True)
        ref_view = cmds.optionMenu(controls["ref_menu"], query=True, value=True)
        use_ray_pose = cmds.checkBox(controls["use_ray_pose"], query=True, value=True)
        filter_edges = cmds.checkBox(controls["filter_edges"], query=True, value=True)
        min_conf = cmds.floatSliderGrp(controls["min_conf"], query=True, value=True)
        max_points = cmds.intFieldGrp(controls["max_points"], query=True, value1=True)

        if not input_folder:
            raise ValueError("Choose an image folder first.")

        model_path = get_model_path(model_name, model_folder)
        if not model_path.exists():
            raise FileNotFoundError(f"Download the model first: {model_path}")

        image_paths = collect_image_paths(input_folder, start_frame, end_frame, frame_stride)
        _set_status_text(controls["status"], f"Running DA3 on {len(image_paths)} images...")
        cmds.refresh()

        prediction = run_inference(
            image_paths,
            model_name=model_name,
            model_folder=model_folder,
            process_res=process_res,
            process_res_method=resize_method,
            use_ray_pose=use_ray_pose,
            ref_view_strategy=ref_view,
        )
        data = prediction_to_dict(prediction, image_paths=image_paths, filter_edges=filter_edges)

        _set_status_text(controls["status"], "Importing into Maya...")
        cmds.refresh()
        root = import_prediction(
            data,
            input_name=source_stem(input_folder),
            output_path=output_folder,
            import_cameras=cmds.checkBox(controls["import_cameras"], query=True, value=True),
            import_points=cmds.checkBox(controls["import_points"], query=True, value=True),
            import_meshes=cmds.checkBox(controls["import_meshes"], query=True, value=True),
            animate_camera=cmds.checkBox(controls["animate_camera"], query=True, value=True),
            keep_individual_cameras=cmds.checkBox(controls["keep_cameras"], query=True, value=True),
            per_frame_geometry=cmds.checkBox(controls["per_frame_geo"], query=True, value=True),
            min_confidence=min_conf,
            max_points=max_points,
        )
        _set_status_text(controls["status"], f"Done. Created {root}")
    except Exception as exc:
        traceback.print_exc()
        _set_status_text(controls["status"], f"Generate failed: {exc}")
