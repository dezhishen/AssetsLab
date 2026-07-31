# AssetsLab Minimal Prototype

Target engine: Godot 4.6.2.

This prototype is intentionally UI-free. It is a command-line validated gameplay slice for:

- four-direction movement;
- eight-frame walk animation;
- collision against arena walls;
- one bomb with a short fuse and blast feedback;
- QQTang-style oversized-head neutral base as the current runtime skin: shared torso, arms, lower-body, feet, plus male/female head layers.
- deterministic front-facing ear and eye/blush layers selected by an appearance seed.

Body source rule: all new body adaptation work uses only
`assets/characters/generated/female_adventurer_reference_mannequin_v1/`.
Other body assets in the repository are legacy or problematic comparison
fixtures and must not be selected for new production art.

Controls:

- `WASD` or arrow keys: move.
- `Space`: place one bomb.

Append `--female` to run the same prototype with the female-presenting base.
Append `--compact` to use the isolated compact-stride candidate assets.
Append `--appearance-seed=12345` to select a repeatable face/ear combination.
Use `-BaseFeatures` on the test scripts to validate the fixed directional
`base_features_v1` set before enabling randomization.

Run from the repository root. The test scripts resolve Godot in this order: `-GodotPath`, `GODOT_BIN`/`GODOT_PATH`, `godot`/`godot4` on `PATH`, then the legacy adjacent `Godot-4.6.2` directory:

```powershell
$env:GODOT_BIN = 'E:\Path\To\Godot_v4.6.2-stable_win64_console.exe'
.\tools\run_headless_tests.ps1 -Female

# Or pass a different local installation for one run:
.\tools\run_headless_tests.ps1 -GodotPath 'E:\Other\Godot\godot.exe' -Female
```

The verified CC0 RGS right-facing walk reference can be loaded into the Godot
smoke test with:

```powershell
.\tools\run_headless_tests.ps1 -RebuildHead -RebuildBody -RgsWalkReference -AppearanceSeed 20260730
```

`-RgsWalkReference` activates the eight-frame RGS motion reference through an
isolated runtime slot. It is not the final character style; the next body pass
will redraw our own art against its pose timing.

Generate a hidden-window W/A/S/D capture and GIF from the repository root:

```powershell
.\tools\capture_walk_gif.ps1
```

Add `-Female` to capture the female-presenting base, `-Compact` to capture the compact-stride candidate, `-RgsWalkReference` to capture the open-source motion reference, or `-MilestoneBodyRight` to capture the frozen pixel-project milestone directly.
Add `-RebuildHead` to capture the calibrated `rebuild_atlas_v1_runtime/male` head on the current body.
Add `-RightOnly` with `-MilestoneBodyRight` to capture only the eight-frame right-facing milestone loop and avoid mixing other direction assets.

Both test entry points generate a fresh random appearance package under
`prototype/test_output/random_appearance/` before starting Godot. The package
contains the selected seed, a composited 4 x 8 walk atlas, individual frames,
and a preview. Pass `-AppearanceSeed 12345` to reproduce one package exactly.
When `-BaseFeatures` is used, the test additionally validates and runs the
non-random base feature set.

The capture script resolves Python from `-PythonPath`, `PYTHON_BIN`, PATH, or the local `.venv`/sibling fallback. Pillow is required for GIF conversion.

`tools/generate_random_appearance.py` creates the ignored per-run package;
`tools/validate_random_appearance.py` verifies that the package frames are
complete, composited, and consistent with the seed/gender rule.

The Godot process uses `--headless` with the Windows/OpenGL renderer, so no editor or game window is presented even if the capture is started repeatedly. PNG frames and the GIF are written to `prototype/test_output/`; this directory is ignored by Git. The GIF is `prototype/test_output/movement_walk.gif`.

The headless test runner validates all 192 frames across six chibi layers and
512 face/ear component frames before launching Godot. It checks fixed frame
size, layer seam ranges, the shared foot baseline, transparent rear appearance
rows, and deterministic seed selection. Add `-Compact` to validate and run the
compact variant.

The generated walk sheets are source assets. The processed transparent atlases
under `assets/characters/chibi/` are the runtime inputs for this prototype. The
runtime stack is independent `Feet` + `LowerBody` + `Arms` + `Torso` + `Ear` +
male/female `Head` + `Face` layers. The first appearance pass has no nose or
mouth; hair and clothing remain future layers.

Open `preview/index.html` for the persistent local asset preview. It uses
project-tracked files instead of `test_output/`, so the page remains usable
after temporary test artifacts are cleaned.

Publish a timestamped snapshot and start a read-only LAN server for phone
review from the repository root:

```powershell
.\tools\serve_preview.ps1 -SnapshotName rear_ear_fix
```

The command prints one or more `http://<LAN-IP>:8765/snapshots/<snapshot>/`
addresses. Each run creates a separate snapshot under the ignored
`prototype/preview/snapshots/` directory, so a previous change can be compared
later without being overwritten.

Stop the background preview server with:

```powershell
.\tools\stop_preview.ps1
```

Preview access rule: when a person needs to inspect a visual result, use the
Tailscale URL printed by the preview server. Local file links, `localhost`,
and temporary chat attachments are not reliable as the only access method.
Whenever Tailscale is used, proactively include the complete preview URL in
the response. If nobody requests visual review, do not generate an additional
preview.

Use the interactive component calibration page at
`http://<Tailscale-IP>:8765/calibrate.html`. It can move the face and ear
parts independently for all four directions and save the calibration JSON to
`prototype/preview/calibration/latest.json`.
