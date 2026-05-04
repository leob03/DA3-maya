# DA3 Maya

Maya tools for running Depth Anything 3 and importing the result as cameras,
point clouds, or depth meshes.

This is a Maya port/scaffold of the DA3 Blender add-on workflow. It keeps the
model/inference side in plain Python and swaps Blender scene creation for Maya
commands/API calls.

## Quick Start

From Maya's Script Editor, run:

```python
import sys
sys.path.insert(0, "/mnt/share/dev-lbringer/camera_tracking/maya_da3/scripts")
import da3_maya
da3_maya.show()
```

## Maya Module Install

To avoid running the Script Editor bootstrap every time, install DA3 Maya as a
user Maya module:

```bash
cd /path/to/DA3-maya
/Applications/Autodesk/maya2024/Maya.app/Contents/bin/mayapy install_maya_module.py
```

Restart Maya, then open DA3 Maya from the Script Editor or a Python shelf
button:

```python
import da3_maya
da3_maya.show()
```

`show()` opens DA3 Maya as a docked Maya workspace panel by default. To use the
older standalone window instead:

```python
import da3_maya
da3_maya.show_floating()
```

The module does not create menu or shelf UI during Maya startup. If you want the
`DA3 Maya` menu, run this after Maya is fully open:

```python
import da3_maya
da3_maya.install_ui()
```

Shelf creation is intentionally opt-in because some Maya setups are sensitive to
shelf edits from scripts. To test it separately:

```python
import da3_maya
da3_maya.install_ui(include_shelf=True)
```

For a module install, copy or symlink `DA3Maya.mod` into one of Maya's module
folders and edit the path line to point at this `maya_da3` directory:

```text
+ DA3Maya 0.1 /mnt/share/dev-lbringer/camera_tracking/maya_da3
PYTHONPATH +:= scripts
```

Then restart Maya and run:

```python
import da3_maya
da3_maya.show()
```

## First Run

1. Open the DA3 Maya window.
2. Click `Install Dependencies`. This uses Maya's Python interpreter.
3. Click `Download Model`.
4. Pick an image folder.
5. Click `Generate`.

On Apple Silicon Macs, `Install Dependencies` uses `requirements-macos.txt`.
The model loader defaults to CPU on macOS because DA3 currently hits PyTorch MPS
operators that are not fully implemented. This is intended as a test/development
path. To experiment with MPS anyway, set `DA3_MAYA_USE_MPS=1` before launching
Maya. For Linux or Windows machines with NVIDIA GPUs, the default
`requirements.txt` keeps the CUDA PyTorch wheel source and the model loader will
prefer CUDA.

For first Mac tests, use `da3-small` or `da3-base`, a low process resolution,
and only a few frames. The final CUDA workstation path can use larger models and
higher resolutions.

## Current Scope

Implemented:

- DA3 model download.
- Dependency install/check.
- Image folder inference.
- Frame range and frame stride.
- DA3 cameras with keyed animation option.
- Combined or per-frame point cloud import.
- Per-frame mesh import from depth.
- Confidence and edge filtering.
- Intrinsics CSV/calib export.

Not yet ported from the Blender add-on:

- DA3 Streaming mode.
- YOLO segmentation split.
- Motion-object split.
- In-Maya progress cancellation.

Those are separable follow-up ports: the inference data structures here already
match the Blender add-on closely enough to add them without changing the Maya
scene import layer much.
