# AssetsLab Minimal Prototype

Target engine: Godot 4.6.2.

This prototype is intentionally UI-free. It is a command-line validated gameplay slice for:

- four-direction movement;
- eight-frame walk animation;
- collision against arena walls;
- one bomb with a short fuse and blast feedback;
- QQTang-style oversized-head neutral base as the current runtime skin: shared body plus male/female head layer.

Controls:

- `WASD` or arrow keys: move.
- `Space`: place one bomb.

Append `--female` to run the same prototype with the female-presenting base.

Run from the repository root. The test scripts resolve Godot in this order: `-GodotPath`, `GODOT_BIN`/`GODOT_PATH`, `godot`/`godot4` on `PATH`, then the legacy adjacent `Godot-4.6.2` directory:

```powershell
$env:GODOT_BIN = 'E:\Path\To\Godot_v4.6.2-stable_win64_console.exe'
.\tools\run_headless_tests.ps1 -Female

# Or pass a different local installation for one run:
.\tools\run_headless_tests.ps1 -GodotPath 'E:\Other\Godot\godot.exe' -Female
```

Generate a hidden-window W/A/S/D capture and GIF from the repository root:

```powershell
.\tools\capture_walk_gif.ps1
```

Add `-Female` to capture the female-presenting base.

The capture script resolves Python from `-PythonPath`, `PYTHON_BIN`, PATH, or the local `E:\env\venv\Scripts\python.exe` fallback.

The Godot process uses the normal OpenGL renderer but is launched hidden, so no editor or game window is presented. PNG frames and the GIF are written to `prototype/test_output/`; this directory is ignored by Git. The GIF is `prototype/test_output/movement_walk.gif`.

The generated walk sheets are source assets. The processed transparent atlases under `assets/characters/chibi/` are the runtime inputs for this prototype. The mannequin has no ears, facial features, hair, or clothing; female blush is reserved for a later independent face overlay.
