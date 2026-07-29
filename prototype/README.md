# AssetsLab Minimal Prototype

Target engine: Godot 4.6.2.

This prototype is intentionally UI-free. It is a command-line validated gameplay slice for:

- four-direction movement;
- four-frame walk animation;
- collision against arena walls;
- one bomb with a short fuse and blast feedback;
- male neutral base as the current runtime skin.

Controls:

- `WASD` or arrow keys: move.
- `Space`: place one bomb.

Append `--female` to run the same prototype with the female-presenting base.

Run from the Godot 4.6.2 executable directory:

```powershell
godot --path D:\Apps\CodeXApp\Tests\AssetsLab\prototype --editor --headless --quit
godot --path D:\Apps\CodeXApp\Tests\AssetsLab\prototype --headless --script res://tests/smoke_test.gd
godot --path D:\Apps\CodeXApp\Tests\AssetsLab\prototype --headless --script res://tests/smoke_test.gd -- --female
```

Generate a hidden-window W/A/S/D capture and GIF from the repository root:

```powershell
.\tools\capture_walk_gif.ps1
```

Add `-Female` to capture the female-presenting base.

The Godot process uses the normal OpenGL renderer but is launched hidden, so no editor or game window is presented. PNG frames and the GIF are written to `prototype/test_output/`; this directory is ignored by Git. The GIF is `prototype/test_output/movement_walk.gif`.

The generated walk sheets are reference assets. The processed transparent atlases under `assets/characters/` are the runtime inputs for this prototype.
