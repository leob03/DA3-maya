"""Maya scene import helpers for DA3 predictions."""

from __future__ import annotations

import csv
import math
import os


def _maya_safe_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
    return cleaned or "DA3"


def _cv_points_to_maya(points):
    """OpenCV/DA3 world axes to Maya Y-up world axes."""
    pts = points.copy()
    pts[..., 1] = -points[..., 1]
    pts[..., 2] = -points[..., 2]
    return pts


def _cv_camera_to_maya_matrix(world_to_camera_3x4):
    import numpy as np

    world_to_camera = np.vstack([world_to_camera_3x4, [0, 0, 0, 1]])
    camera_to_world = np.linalg.inv(world_to_camera)
    world_fix = np.diag([1.0, -1.0, -1.0, 1.0])
    local_fix = np.diag([1.0, -1.0, -1.0, 1.0])
    return world_fix @ camera_to_world @ local_fix


def _set_transform_matrix(node: str, matrix):
    from maya import cmds

    cmds.xform(node, ws=True, matrix=[float(v) for v in matrix.reshape(-1)])


def _ensure_group(name: str) -> str:
    from maya import cmds

    safe_name = _maya_safe_name(name)
    if cmds.objExists(safe_name):
        return safe_name
    return cmds.group(empty=True, name=safe_name)


def _key_visibility(node: str, frame: int):
    from maya import cmds

    for key_frame, visible in ((0, False), (frame, True), (frame + 1, False)):
        cmds.currentTime(key_frame, edit=True)
        cmds.setAttr(f"{node}.visibility", visible)
        cmds.setKeyframe(node, attribute="visibility", time=key_frame)


def create_cameras(
    predictions: dict,
    parent: str | None = None,
    image_width: int | None = None,
    image_height: int | None = None,
    animate_sequence: bool = True,
    keep_individual_cameras: bool = False,
    output_path: str | None = None,
    source_name: str = "da3",
):
    from maya import cmds
    import numpy as np

    images = predictions.get("images")
    if image_width is None or image_height is None:
        image_height, image_width = images.shape[1:3]

    extrinsics = predictions["extrinsic"]
    intrinsics = predictions["intrinsic"]
    image_paths = predictions.get("image_paths", [])
    if len(extrinsics) != len(intrinsics):
        raise ValueError("Extrinsic and intrinsic lists must have the same length.")

    camera_group = _ensure_group(f"DA3_{source_name}_Cameras")
    if parent:
        cmds.parent(camera_group, parent)

    animated_camera = None
    animated_shape = None
    if animate_sequence:
        animated_camera, animated_shape = cmds.camera(name=_maya_safe_name(f"DA3_{source_name}_Camera"))
        cmds.parent(animated_camera, camera_group)

    records = []
    for i, ext in enumerate(extrinsics):
        k = intrinsics[i]
        fx = float(k[0, 0])
        fy = float(k[1, 1])
        cx = float(k[0, 2])
        cy = float(k[1, 2])
        frame = i + 1
        if i < len(image_paths):
            from .processing import frame_number_from_path

            frame = frame_number_from_path(image_paths[i], i)
            cam_name = os.path.splitext(os.path.basename(image_paths[i]))[0]
        else:
            cam_name = f"Camera_{i:04d}"

        cam, shape = cmds.camera(name=_maya_safe_name(f"DA3_{source_name}_{cam_name}"))
        cmds.parent(cam, camera_group)
        _apply_camera_intrinsics(shape, fx, fy, cx, cy, image_width, image_height)
        matrix = _cv_camera_to_maya_matrix(ext)
        _set_transform_matrix(cam, matrix)

        records.append(
            {
                "frame": frame,
                "name": cam,
                "fx": fx,
                "fy": fy,
                "cx": cx,
                "cy": cy,
                "fov_h_deg": math.degrees(2.0 * math.atan(image_width / (2.0 * fx))),
                "fov_v_deg": math.degrees(2.0 * math.atan(image_height / (2.0 * fy))),
            }
        )

        if animated_camera:
            _apply_camera_intrinsics(animated_shape, fx, fy, cx, cy, image_width, image_height)
            _set_transform_matrix(animated_camera, matrix)
            cmds.setKeyframe(animated_camera, attribute="translate", time=frame)
            cmds.setKeyframe(animated_camera, attribute="rotate", time=frame)
            cmds.setKeyframe(animated_shape, attribute="focalLength", time=frame)

        if animate_sequence and not keep_individual_cameras:
            cmds.delete(cam)

    if animated_camera:
        cmds.lookThru(animated_camera)

    if records:
        cmds.playbackOptions(minTime=min(r["frame"] for r in records), maxTime=max(r["frame"] for r in records))
        _write_intrinsics(records, image_width, image_height, output_path, source_name)

    return animated_camera


def _apply_camera_intrinsics(shape: str, fx: float, fy: float, cx: float, cy: float, image_width: int, image_height: int):
    from maya import cmds

    horizontal_aperture = image_width / 25.4
    vertical_aperture = image_height / 25.4
    cmds.setAttr(f"{shape}.horizontalFilmAperture", horizontal_aperture)
    cmds.setAttr(f"{shape}.verticalFilmAperture", vertical_aperture)
    cmds.setAttr(f"{shape}.focalLength", fx)
    cmds.setAttr(f"{shape}.filmFit", 1)
    try:
        cmds.setAttr("defaultResolution.width", image_width)
        cmds.setAttr("defaultResolution.height", image_height)
    except Exception:
        pass

    # Maya film offsets are in inches. Positive horizontal shifts right.
    h_offset = ((cx - image_width / 2.0) / image_width) * horizontal_aperture
    v_offset = ((cy - image_height / 2.0) / image_height) * vertical_aperture
    cmds.setAttr(f"{shape}.horizontalFilmOffset", h_offset)
    cmds.setAttr(f"{shape}.verticalFilmOffset", -v_offset)


def _write_intrinsics(records: list[dict], image_width: int, image_height: int, output_path: str | None, source_name: str):
    if not output_path:
        return

    import numpy as np

    os.makedirs(output_path, exist_ok=True)
    csv_path = os.path.join(output_path, "camera_intrinsics.csv")
    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["frame", "name", "fx", "fy", "cx", "cy", "fov_h_deg", "fov_v_deg"])
        writer.writeheader()
        writer.writerows(records)

    fx = float(np.median([r["fx"] for r in records]))
    fy = float(np.median([r["fy"] for r in records]))
    cx = float(np.median([r["cx"] for r in records]))
    cy = float(np.median([r["cy"] for r in records]))
    stem = os.path.splitext(source_name)[0] or "da3"
    with open(os.path.join(output_path, f"calib_{stem}_da3.txt"), "w") as fh:
        fh.write(f"{fx:.6f} {fy:.6f} {cx:.6f} {cy:.6f}\n")


def create_point_cloud(
    predictions: dict,
    parent: str | None = None,
    min_confidence: float = 0.5,
    per_frame: bool = False,
    max_points: int = 250000,
    source_name: str = "da3",
):
    from maya import cmds
    import numpy as np

    points = predictions["world_points_from_depth"]
    colors = predictions["images"]
    conf = predictions["conf"]
    image_paths = predictions.get("image_paths", [])
    group = _ensure_group(f"DA3_{source_name}_PointClouds")
    if parent:
        cmds.parent(group, parent)

    def make_particle(name, pts, cols, frame=None):
        if len(pts) == 0:
            return None
        obj = _create_colored_particle_cloud(_maya_safe_name(name), pts, cols)
        cmds.parent(obj, group)
        if frame is not None:
            _key_visibility(obj, frame)
        return obj

    if per_frame:
        for i in range(points.shape[0]):
            flat_points, flat_colors = _filtered_points(points[i], colors[i], conf[i], min_confidence)
            flat_points, flat_colors = _limit_points(flat_points, flat_colors, max_points)
            frame = i + 1
            name = f"DA3_{source_name}_Points_{i:04d}"
            if i < len(image_paths):
                from .processing import frame_number_from_path

                frame = frame_number_from_path(image_paths[i], i)
                name = f"DA3_{source_name}_Points_{os.path.splitext(os.path.basename(image_paths[i]))[0]}"
            make_particle(name, flat_points, flat_colors, frame=frame)
        return group

    flat_points, flat_colors = _filtered_points(points.reshape(-1, 3), colors.reshape(-1, 3), conf.reshape(-1), min_confidence)
    flat_points, flat_colors = _limit_points(flat_points, flat_colors, max_points)
    make_particle(f"DA3_{source_name}_Points", flat_points, flat_colors)
    return group


def _filtered_points(points, colors, conf, min_confidence):
    mask = conf.reshape(-1) >= float(min_confidence)
    pts = _cv_points_to_maya(points.reshape(-1, 3))[mask]
    cols = colors.reshape(-1, 3)[mask]
    return pts, cols


def _limit_points(points, colors, max_points):
    if max_points <= 0 or len(points) <= max_points:
        return points, colors
    import numpy as np

    idx = np.linspace(0, len(points) - 1, max_points, dtype=np.int64)
    return points[idx], colors[idx]


def _create_colored_particle_cloud(name: str, points, colors):
    from maya import cmds

    obj = cmds.particle(name=name)[0]
    shape = cmds.listRelatives(obj, shapes=True, fullPath=True)[0]

    try:
        if not cmds.attributeQuery("rgbPP", node=shape, exists=True):
            cmds.addAttr(shape, longName="rgbPP", dataType="vectorArray")
        if not cmds.attributeQuery("rgbPP0", node=shape, exists=True):
            cmds.addAttr(shape, longName="rgbPP0", dataType="vectorArray")

        chunk_size = 5000
        for start in range(0, len(points), chunk_size):
            end = min(start + chunk_size, len(points))
            cmds.emit(
                object=obj,
                position=[tuple(map(float, p)) for p in points[start:end]],
                attribute="rgbPP",
                vectorValue=[tuple(map(float, c[:3])) for c in colors[start:end]],
            )

        # 3 is the classic point render type. Viewport 2.0 should display rgbPP
        # in shaded/color modes once the attribute exists on the particle shape.
        if cmds.attributeQuery("particleRenderType", node=shape, exists=True):
            cmds.setAttr(f"{shape}.particleRenderType", 3)
    except Exception as exc:
        print(f"[DA3 Maya] Could not create colored particles, falling back to uncolored points: {exc}")
        cmds.delete(obj)
        obj = cmds.particle(p=[tuple(map(float, p)) for p in points], name=name)[0]

    return obj


def create_depth_meshes(
    predictions: dict,
    parent: str | None = None,
    min_confidence: float = 0.5,
    per_frame: bool = True,
    source_name: str = "da3",
):
    from maya import cmds
    import maya.api.OpenMaya as om
    import numpy as np

    points = predictions["world_points_from_depth"]
    colors = predictions["images"]
    conf = predictions["conf"]
    image_paths = predictions.get("image_paths", [])

    group = _ensure_group(f"DA3_{source_name}_Meshes")
    if parent:
        cmds.parent(group, parent)

    n_frames, height, width, _ = points.shape
    rr, cc = np.meshgrid(np.arange(height - 1), np.arange(width - 1), indexing="ij")
    v0 = rr * width + cc
    v1 = rr * width + (cc + 1)
    v2 = (rr + 1) * width + (cc + 1)
    v3 = (rr + 1) * width + cc
    faces = np.stack([v0, v1, v2, v3], axis=-1).reshape(-1, 4)

    made = []
    for i in range(n_frames):
        pts = _cv_points_to_maya(points[i].reshape(-1, 3))
        cols = colors[i].reshape(-1, 3)
        confs = conf[i].reshape(-1)
        face_mask = (
            (confs[faces[:, 0]] >= min_confidence)
            & (confs[faces[:, 1]] >= min_confidence)
            & (confs[faces[:, 2]] >= min_confidence)
            & (confs[faces[:, 3]] >= min_confidence)
        )
        used_faces = faces[face_mask]
        if len(used_faces) == 0:
            continue

        used_vertices = np.unique(used_faces)
        remap = np.full(len(pts), -1, dtype=np.int64)
        remap[used_vertices] = np.arange(len(used_vertices))
        mesh_points = [om.MPoint(float(x), float(y), float(z)) for x, y, z in pts[used_vertices]]
        face_counts = [4] * len(used_faces)
        face_connects = remap[used_faces].reshape(-1).astype(int).tolist()

        mesh_fn = om.MFnMesh()
        mesh_fn.create(mesh_points, face_counts, face_connects)
        base_name = f"Mesh_{i:04d}"
        frame = i + 1
        if i < len(image_paths):
            from .processing import frame_number_from_path

            base_name = os.path.splitext(os.path.basename(image_paths[i]))[0]
            frame = frame_number_from_path(image_paths[i], i)
        shape_path = mesh_fn.fullPathName()
        parent_nodes = cmds.listRelatives(shape_path, parent=True, fullPath=True) or []
        node = parent_nodes[0] if parent_nodes else shape_path
        node = cmds.rename(node, _maya_safe_name(f"DA3_{source_name}_{base_name}_Mesh"))
        cmds.parent(node, group)

        try:
            color_array = om.MColorArray([om.MColor((float(c[0]), float(c[1]), float(c[2]), 1.0)) for c in cols[used_vertices]])
            mesh_fn.setVertexColors(color_array, list(range(len(used_vertices))))
            shape = cmds.listRelatives(node, shapes=True, fullPath=True)[0]
            cmds.setAttr(f"{shape}.displayColors", 1)
        except Exception as exc:
            print(f"[DA3 Maya] Could not assign mesh vertex colors: {exc}")

        if per_frame:
            _key_visibility(node, frame)
        made.append(node)
    return made


def import_prediction(
    predictions: dict,
    input_name: str,
    output_path: str | None = None,
    import_cameras: bool = True,
    import_points: bool = True,
    import_meshes: bool = False,
    animate_camera: bool = True,
    keep_individual_cameras: bool = False,
    per_frame_geometry: bool = False,
    min_confidence: float = 0.5,
    max_points: int = 250000,
):
    from maya import cmds

    source_name = _maya_safe_name(input_name)
    root = _ensure_group(f"DA3_{source_name}")

    if import_cameras:
        create_cameras(
            predictions,
            parent=root,
            animate_sequence=animate_camera,
            keep_individual_cameras=keep_individual_cameras,
            output_path=output_path,
            source_name=source_name,
        )
    if import_points:
        create_point_cloud(
            predictions,
            parent=root,
            min_confidence=min_confidence,
            per_frame=per_frame_geometry,
            max_points=max_points,
            source_name=source_name,
        )
    if import_meshes:
        create_depth_meshes(
            predictions,
            parent=root,
            min_confidence=min_confidence,
            per_frame=per_frame_geometry,
            source_name=source_name,
        )

    cmds.select(root, replace=True)
    return root
