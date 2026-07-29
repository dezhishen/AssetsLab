# AssetsLab Project

## Working Directory

`D:\Apps\CodeXApp\Tests\AssetsLab`

All project work and project files must be kept within this directory.

## File Naming Convention

Use English names for all files.

## Art Experiment Workflow

### Current Direction Decision

Use four directions for the first production experiment: front, right, back, and left. This keeps directional alignment, collision footprint, and modular attachment points easier to control. Expand to eight directions only after the four-direction base is validated.

### Character Architecture

Build one shared modular geometry standard with two presentation variants:

- Male-presenting base: shared head/body proportions with masculine styling layers.
- Female-presenting base: the same canvas, scale, baseline, collision footprint, and attachment points, with subtle feminine proportion cues.

Keep gender presentation out of the neutral mannequin wherever possible. Treat blush as an independent female face-layer marker that can be enabled or replaced later.

### Completed Steps

1. Created front-facing visual anchors for the male-presenting and female-presenting variants.
2. Created four-direction neutral mannequin sheets for both variants. Each sheet includes full-body turns plus separate head-only and body-only turn rows.

The neutral base has no hair, eyes, nose, mouth, clothing, underwear, accessories, or anatomical detail. The front-facing anchors may include eyes and clothing for visual design reference, but no nose or mouth.

### Generated Assets

- `front-character-anchor.png` - male-presenting front design anchor.
- `front-character-anchor-female.png` - female-presenting front design anchor with detachable blush marker.
- `base-mannequin-4way-sheet.png` - male-presenting neutral four-direction base sheet.
- `base-mannequin-4way-female-sheet.png` - female-presenting neutral four-direction base sheet.
- `walk-base-4way-male-4frame-sheet.png` - male-presenting neutral four-direction walk-cycle reference.
- `walk-base-4way-female-4frame-sheet.png` - female-presenting neutral four-direction walk-cycle reference.

### Deferred Work

Do not build the random face, hair, or clothing generation pipeline yet. First validate the four-direction alignment, layer boundaries, scale, and attachment points. Random generation should consume these validated layers as constrained references or seeds.

## Walking Base Execution Plan

### Animation Specification

- Direction set: front, right, back, left.
- First cycle: four frames per direction.
- Frame order: left contact, passing, right contact, passing.
- Motion: small readable leg stride, opposite arm swing, restrained body bob, and a stable head anchor.
- Layout: one 4 x 4 sheet per presentation variant; rows are directions and columns are frames.
- Base content: no hair, eyes, nose, mouth, clothing, underwear, accessories, or anatomical detail.

### Execution Steps

1. Generate the male-presenting neutral walk-cycle sheet from the existing male mannequin as the alignment reference.
2. Generate the female-presenting neutral walk-cycle sheet from the existing female mannequin while preserving the same frame bounds, baseline, head anchor, and collision footprint.
3. Check that every frame keeps the same total height, head diameter, torso attachment, foot baseline, and direction order.
4. Use the sheets as animation references first. Only after the key poses are accepted should they be sliced, retimed, and converted into runtime sprites.

### Acceptance Criteria

The walk must read clearly at small size, loop without a visible pop, keep the head from drifting, avoid foot sliding at contact poses, and remain visually compatible with the standing mannequin sheets.

### Generation Tool

The current raster assets were generated with the built-in `image_gen` workflow and copied into this project directory for reuse.

## Godot Integration Notes

### Target Engine

The target runtime is Godot 4.6.2. The reference checkout at `../BomboAdvantureRef` currently declares Godot 4.7 in its `project.godot`, so engine-version compatibility must be verified before importing these assets into the game project. Do not upgrade the project implicitly during asset work.

### Recommended Runtime Structure

Use one gameplay root and one synchronized visual stack:

- `CharacterBody2D` or the project's existing character root handles movement and collision.
- A `CharacterVisual` child owns the visual layers.
- Each layer is a `Sprite2D` using the same cell size, origin, 4-column frame grid, and 4-row direction grid.
- Suggested layers: `Body`, `Face`, `Hair`, `Clothing`, and optional `Accessory`.
- One controller stores `direction` and `walk_frame`, then applies the same `frame_coords` to every layer. This prevents random layers from drifting out of sync.
- Use `AnimatedSprite2D` with `SpriteFrames` when a character is already flattened into a single composite animation.

This layered `Sprite2D` approach is preferred for the planned random face, hair, and clothing system. Godot 4.6 supports sprite-sheet regions and frame coordinates on `Sprite2D`, while `AnimatedSprite2D` is better suited to a preassembled frame list.

### Asset Handoff Rule

The current walk sheets are reference sheets, not runtime-ready atlases: they contain a neutral background and guide grid. The next art-processing step must isolate each cell, remove the guide/background, preserve a common origin, and export layer-specific sheets before creating Godot resources.

Recommended animation names are `idle_front`, `idle_right`, `idle_back`, `idle_left`, `walk_front`, `walk_right`, `walk_back`, and `walk_left`. The current walk-cycle reference uses four frames per `walk_*` animation.

## Minimal Prototype Status

The first runtime processing pass is complete for the neutral body layer:

- Each walk sheet is split conceptually into a 4 x 4 atlas with 384 x 256 cells.
- Gray background and guide lines were removed with local image processing.
- Transparent runtime atlases, individual frames, idle atlases, and JSON manifests were created under `prototype/assets/characters/`.
- `prototype/` contains a UI-free Godot 4.6.2 test project with movement, collision walls, four-direction walk animation, and a simplified bomb fuse/blast feedback.
- The same prototype can select the female base with the `--female` command-line argument.

### Silent Verification

The Godot 4.6.2 console executable was downloaded to the sibling directory `D:\Apps\CodeXApp\Tests\Godot-4.6.2` and used without opening the editor UI.

Verified commands:

- headless project import: passed;
- male smoke test: `SMOKE_TEST_PASS`;
- female smoke test: `SMOKE_TEST_PASS`;
- two-second headless main-scene launch: passed.

The current prototype validates the movement and asset handoff path. It is not yet the production character system and does not include random face, hair, or clothing layers.

### Prototype Iteration 1 Fixes

- Corrected the generated side-view row mapping so left and right movement face the expected direction.
- Switched runtime playback from the large 4 x 4 atlas to the isolated frame PNGs, preventing adjacent-frame bleed and the stray head fragment visible when moving upward.
- Confirmed that the walk timer advances the actual texture frame while movement continues.
- Reprocessed transparent frames with edge-color extrusion to reduce filtered halos and particle-like edge noise.

### Automated Visual Capture

`tools/capture_walk_gif.ps1` runs `prototype/tests/capture_test.gd` with internal W/A/S/D key events, captures the rendered viewport at 12 FPS, and uses the local Pillow tool environment to produce `prototype/test_output/movement_walk.gif`. Godot is launched as a hidden process with the normal OpenGL renderer because Godot's dummy `--headless` renderer has no readable viewport texture on this machine. The test still runs without presenting an editor or game window.
