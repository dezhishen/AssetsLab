# AssetsLab Minimal Prototype

Target engine: Godot 4.7.

This prototype is intentionally UI-free. It is a command-line validated gameplay slice for:

- four-direction movement;
- eight-frame walk animation;
- collision against arena walls;
- one bomb with a short fuse and blast feedback;
- QQTang-style oversized-head neutral base as the current runtime skin: shared torso, arms, lower-body, feet, plus male/female head layers.
- deterministic front-facing ear and eye/blush layers selected by an appearance seed.

Body source rule: new horizontal walk work starts from the recommended neutral
base `assets/characters/walk_base/walk-base-4way-male-4frame-sheet.png`. The current eight-frame review
candidate is `assets/characters/generated/recommended_base_horizontal_layer_fix_v1/`.
The later `female_adventurer_reference_mannequin_v1_adapted` output is a redraw
comparison fixture and must not be treated as the recommended base.

The generated front/back vertical movement candidate is kept separately at
`assets/characters/generated/body_vertical_update_v1/runtime/`; it is a review
candidate and does not replace the current runtime body. The complete reference
package on the `history0731` branch contains diagonal timing strips, but the
prototype remains four-direction until that contract is stable.

A four-direction walk GIF is written to `prototype/test_output/movement_walk.gif`
when `python workflow/tools/assetslab.py capture-walk` is run. The
four-direction clothed style experiment from the external pixel-art skill is
preview-only and is stored under
`assets/characters/generated/skill_pixel_art_experiment_v1/`.

The new skeleton-first walk workflow is independent of the older body
candidates. Its current first gate is a front-view static skeleton. Run:

```bash
python workflow/tools/assetslab.py stage front skeleton
```

This uses the Godot console executable with `--headless`, writes
`test_output/skeleton_pipeline/front_base.png`, and must pass before the
eight-frame leg loop is started.

The current active step is the leg-only front-view loop. Run:

```bash
python workflow/tools/assetslab.py stage front legs
```

It writes eight independent captures plus
`test_output/skeleton_pipeline/front_legs.gif`. Pelvis, arms, torso, and head
must remain static in this step.

The next isolated step adds only the pelvis bob over those accepted leg frames:

```bash
python workflow/tools/assetslab.py stage front pelvis
```

It writes eight captures plus `test_output/skeleton_pipeline/front_pelvis_bob.gif`.
The pelvis moves vertically by at most 6px peak-to-peak; the head and arms stay
static, and each foot position must exactly match stage 2.

The final front-view skeleton step adds only opposite arm swings:

```bash
python workflow/tools/assetslab.py stage front arms
```

It writes eight captures plus `test_output/skeleton_pipeline/front_arm_swing.gif`.
Hands must remain below their shoulders and on their own side of the center
axis; all accepted stage-3 lower-body values remain unchanged.

The first side-view gate is deliberately static:

```bash
python workflow/tools/assetslab.py stage side skeleton
```

It writes `test_output/skeleton_pipeline/side_base.png`. The capture must show
one right-facing profile, a shared foot baseline, and explicit front/rear limb
depth before the side-view leg loop is created.

The next isolated side step is the leg-only loop:

```bash
python workflow/tools/assetslab.py stage side legs
```

It writes eight captures plus `test_output/skeleton_pipeline/side_legs.gif`.
F0/F4 are contact frames; only the rear leg lifts during F1–F3 and only the
front leg lifts during F5–F7. The pelvis and arms remain static.

The next side step adds only the pelvis bob:

```bash
python workflow/tools/assetslab.py stage side pelvis
```

It writes eight captures plus `test_output/skeleton_pipeline/side_pelvis_bob.gif`.
The pelvis moves vertically by at most 6px peak-to-peak while all side-leg foot
coordinates and upper-body coordinates remain unchanged.

The final side-view step adds only counterphased arms:

```bash
python workflow/tools/assetslab.py stage side arms
```

It writes eight captures plus `test_output/skeleton_pipeline/side_arm_swing.gif`.
The arms are opposite each other and counterphased to the legs; all accepted
side pelvis, foot, and depth-order keys remain unchanged.

## Skeleton Pipeline Status

Paused after the back-view eight-frame leg loop. Remaining: back pelvis/arms,
verified left mirror, four-direction anchor review, body blocks, calibrated
head attachment, and modular male/female face-hair-clothing layers.

Controls:

- `WASD` or arrow keys: move.
- `Space`: place one bomb.

Append `--female` to run the same prototype with the female-presenting base.
Append `--compact` to use the isolated compact-stride candidate assets.
Append `--appearance-seed=12345` to select a repeatable face/ear combination.
Use `--base-features` on the test scripts to validate the fixed directional
`base_features_v1` set before enabling randomization.

Run from the repository root. The test scripts resolve Godot in this order: `--godot`, `GODOT_BIN`/`GODOT_PATH`, `godot`/`godot4` on `PATH`, then the legacy adjacent `Godot-4.7` directory:

```bash
# Point GODOT_BIN at a Godot 4.7 executable (any platform), then run:
GODOT_BIN=/path/to/godot python workflow/tools/assetslab.py test --female

# Or pass a different local installation for one run:
python workflow/tools/assetslab.py test --godot /path/to/godot --female
```

The verified CC0 RGS right-facing walk reference can be loaded into the Godot
smoke test with:

```bash
python workflow/tools/assetslab.py test --rebuild-head --rebuild-body --rgs-walk-reference --appearance-seed 20260730
```

`--rgs-walk-reference` activates the eight-frame RGS motion reference through an
isolated runtime slot. It is not the final character style; the next body pass
will redraw our own art against its pose timing.

Generate a hidden-window W/A/S/D capture and GIF from the repository root:

```bash
python workflow/tools/assetslab.py capture-walk
```

Add `--female` to capture the female-presenting base, `--compact` to capture the compact-stride candidate, `--rgs-walk-reference` to capture the open-source motion reference, or `--milestone-body-right` to capture the frozen pixel-project milestone directly.
Add `--rebuild-head` to capture the calibrated `rebuild_atlas_v1_runtime/male` head on the current body.
Combine it with `--latest-generated-body` to validate the latest generated body
adapter under `assets/characters/generated/female_adventurer_reference_mannequin_v1_adapted/`.
Use `--vertical-candidate --vertical-only` to capture only the generated front/back
vertical candidate, without mixing it with the four-direction runtime body.
Add `--right-only` with `--milestone-body-right` to capture only the eight-frame right-facing milestone loop and avoid mixing other direction assets.

Both test entry points generate a fresh random appearance package under
`prototype/test_output/random_appearance/` before starting Godot. The package
contains the selected seed, a composited 4 x 8 walk atlas, individual frames,
and a preview. Pass `--appearance-seed 12345` to reproduce one package exactly.
When `--base-features` is used, the test additionally validates and runs the
non-random base feature set.

The capture script resolves Python from `--python`, `PYTHON_BIN`, PATH, or the local `.venv`/sibling fallback. Pillow is required for GIF conversion.

Build the candidate vertical frames and structure-preserving skin previews from
the repository root:

```bash
python workflow/tools/build_body_vertical_update.py
python workflow/tools/recolor_body_palettes.py
```

The palette tool writes `light`, `warm`, and `deep` variants while preserving
the source frame size and alpha mask byte-for-byte. These are preview assets;
they are not wired into the player yet.

`workflow/tools/generate_random_appearance.py` creates the ignored per-run package;
`workflow/tools/validate_random_appearance.py` verifies that the package frames are
complete, composited, and consistent with the seed/gender rule.

The Godot process uses `--headless` with the Windows/OpenGL renderer, so no editor or game window is presented even if the capture is started repeatedly. The resolver requires a `_console.exe` build; it fails closed if a GUI binary has no unambiguous console sibling. PNG frames and the GIF are written to `prototype/test_output/`; this directory is ignored by Git. The GIF is `prototype/test_output/movement_walk.gif`.

The headless test runner validates all 192 frames across six chibi layers and
512 face/ear component frames before launching Godot. It checks fixed frame
size, layer seam ranges, the shared foot baseline, transparent rear appearance
rows, and deterministic seed selection. Add `--compact` to validate and run the
compact variant.

The generated walk sheets are source assets. The processed transparent atlases
under `assets/characters/chibi/` are the runtime inputs for this prototype. The
runtime stack is independent `Feet` + `LowerBody` + `Arms` + `Torso` + `Ear` +
male/female `Head` + `Face` layers. The first appearance pass has no nose or
mouth; hair and clothing remain future layers.

This `prototype/` is a pure Godot preview demo — there is no HTML preview
pipeline. The demo runs against an exported artifact package under
`dist/<workflow_id>/` (layered `atlas/` + `runtime_manifest.json` +
`character_walk_4way.gif`), produced either by the workflow's final
「导出 Godot 制品」step (`workflow/tools/export_artifacts.py`) or by baking a
skin with `workflow/tools/export_skin_demo.py --skin <name>` (procedural
skin → demo artifact, e.g. `dist/orc/`):

```bash
# from the repository root, point the demo at an artifact package:
godot --path prototype -- --artifacts dist/orc          # space or `=` both work
godot --path prototype -- --artifacts=dist/orc
```

`prototype/scripts/player.gd` reads `runtime_manifest.json` and
`atlas/<layer>/walk_row<row>_frame<frame>.png` at startup (prints
`ARTIFACTS_LOADED dir=… layers=7 frames=224` on success); without
`--artifacts` it falls back to the bundled
`assets/characters/rebuild_atlas_v1_runtime/male/` runtime. The demo keeps
interactive movement (WASD/arrows) and bomb placement (Space). A skin's own
preview animation can be played with `--skin-mode --skin-pack=<name>`.
