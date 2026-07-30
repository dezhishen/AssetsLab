# AssetsLab Project

## Working Directory

`D:\Apps\CodeXApp\Tests\AssetsLab`

All project work and project files must be kept within this directory.

## File Naming Convention

Use English names for all files.

## Preview Access Principle

When a developer or reviewer needs to see a generated preview, publish it
through the Tailscale address of the local preview server. Do not rely on a
local file link, `localhost`, or a temporary chat attachment as the only
preview channel. Whenever Tailscale is used, proactively provide the complete
preview URL in the response. If preview review is not requested or needed, do
not spend time generating or publishing an additional preview; silent
headless tests remain sufficient.

## Development Status

Last updated: 2026-07-31.

### Current Production Candidate

- Runtime animation uses synchronized per-frame `Sprite2D` layers in Godot 4.6.2.
- The first production experiment remains four directions: front, right, back, left.
- The verified CC0 RGS modular character is integrated only as an eight-frame
  right-facing motion reference under `prototype/assets/characters/open_source/`.
- The next art task is to redraw our own QQTang-style body against the same eight
  pose phases. The RGS pixels are not the final art style.
- Hair and clothing remain deferred until the body cycle and anchors are stable.

### Failed Candidates Retired From Runtime

- Skeleton2D/Polygon2D keyframe rig: retired because bitmap parts warped and
  produced unclear leg motion, head drift, and particle-like edge artifacts.
- `WalkReadyRight` baked training sample: retired because it was a single
  generated direction and did not provide a coherent four-direction base.
- Walk-motion proxy and full-walk generated samples: no longer part of the
  runtime, test runner, or published preview.
- The reusable lesson from these candidates is pose timing and contact-frame
  structure, not their generated pixels.

### Verification Progress

- Random appearance package: passed with deterministic seed validation.
- Godot 4.6.2 import and smoke tests: passed.
- RGS reference loading: passed with eight runtime frames.
- Hidden W/A/S/D capture: passed with 36 frames and GIF conversion.
- GitHub synchronization: pending this cleanup and verification pass.

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

The neutral base has no hair, ears, eyes, nose, mouth, clothing, underwear, accessories, or anatomical detail. The head is intentionally oversized in the QQTang/Q-style proportion, with a compact body beneath it. The front-facing anchors may include eyes and clothing for visual design reference, but no nose or mouth.

### Generated Assets

- `front-character-anchor.png` - male-presenting front design anchor.
- `front-character-anchor-female.png` - female-presenting front design anchor with detachable blush marker.
- `base-mannequin-4way-sheet.png` - male-presenting neutral four-direction base sheet.
- `base-mannequin-4way-female-sheet.png` - female-presenting neutral four-direction base sheet.
- `walk-base-4way-male-4frame-sheet.png` - male-presenting neutral four-direction walk-cycle reference.
- `walk-base-4way-female-4frame-sheet.png` - female-presenting neutral four-direction walk-cycle reference.
- `prototype/assets/characters/generated/character_turnaround_v1_male.png` - first male-presenting four-direction character turnaround generated from the male front anchor.
- `prototype/assets/characters/turnaround_v1/` - rough aligned split of the turnaround into `face_base`, `eyes`, `eyebrows`, `ears`, and `hair` layers, with a `full` reference layer for comparison.
- `prototype/assets/characters/generated/character_head_rebuild_v1_male.png` - clean head-only four-direction reference used to begin component reconstruction.
- `prototype/assets/characters/rebuilt_head_v1/` - intermediate head-only reconstruction reference; retained for comparison, not the preferred runtime input.
- `prototype/assets/characters/generated/neutral_face_base_rebuild_v1_male.png` - independently generated featureless four-direction face base.
- `prototype/assets/characters/generated/facial_feature_atlas_rebuild_v1_male.png` - independently generated eyes, eyebrows, and ears atlas.
- `prototype/assets/characters/generated/hair_atlas_rebuild_v1_male.png` - independently generated hair atlas, currently provisional because its fit still needs anchor correction.
- `prototype/assets/characters/rebuild_atlas_v1/` - fixed-frame components produced from the independent base and feature atlases.
- `prototype/assets/characters/rebuild_atlas_v1_runtime/male/` - 64 x 64 runtime sheets used by the silent `--rebuild-head` Godot test; hair is intentionally excluded until its fit is approved.
- `prototype/preview/index.html` - persistent local preview page; it uses tracked project assets rather than temporary test output.

The turnaround split is an alignment study, not production-ready randomization
art. Its manifest records the directional feature policy: two eyes on the
front, one eye on each side, and no eyes or eyebrows on the back. The source
is intentionally kept as a complete visual reference until the masks are
redrawn and manually checked.

The head rebuild separates the problem from body and clothing occlusion. The
current preferred direction is independent reconstruction: the neutral face
base, facial feature atlas, and hair atlas are generated as separate inputs.
All component layers use one union frame per direction; they must not be
scaled independently. `rebuild_atlas_v1` remains a reference reconstruction
until the component edges and attachment anchors receive manual art review.

The Godot smoke test can load the reconstructed face layers with
`tools/run_headless_tests.ps1 -RebuildHead`. It reuses the existing body and
walk animation, repeats the static reconstructed face across eight body frames,
and leaves hair disabled while its coverage is being corrected.

### Anchor-Based Component Registration

Runtime component placement now uses `head_contour_anchors_v1` in
`rebuild_atlas_v1_runtime/male/runtime_manifest.json`. The neutral head alpha
provides the direction-specific contour, center, top, neck, and side-edge
anchors. Face and ear layers declare their target anchors in the same 64 x 64
runtime space, and the builder computes the required registration shift from
the component alpha center. Front and rear ears use separate left/right
anchors; side views use one visible-ear anchor. This is the intended contract
for future hair and clothing layers.

The reconstructed runtime keeps the Godot movement rows explicit: row 1 is the
right-facing base and row 3 is the left-facing base. The detachable side face
and ear sources are exchanged 2/4 at build time without an additional
horizontal mirror, because the generated source atlas had those side features
reversed.

### Appearance Pipeline Status

The first deterministic appearance pass is now implemented after reviewing the
`test_gen_human` branch of the BomboAdvanture reference project. AssetsLab
adopts its useful ideas—stable seeds, component manifests, and direction-aware
draw layers—while keeping the current 64 x 64, 4 x 8 runtime format.

- `ears` and `eyes/optional_blush` are independent runtime layers.
- Eight face/ear combinations are generated offline and indexed by one
  `appearance_seed`.
- The first pass places these overlays on the front direction only. Side and
  rear views remain transparent until direction-specific ear/face art is ready.
- Nose and mouth are explicitly excluded from the manifest and generated
  layers.
- Hair and clothing remain deferred; clothing will be introduced as complete
  outfit kits first, then split into replacement slots after alignment is
  proven.

The image generation step is offline. Godot only selects already processed
assets at runtime, so gameplay remains deterministic and does not depend on an
AI service.

## Walking Base Execution Plan

### Authoritative Limb-Puzzle Contract

The user-authored rectangle pose contract is the source of truth for the
right-facing body redraw. It exists to prevent image generation from guessing
which projected arm or leg is visible, and to make the intended occlusion
explicit before any final pixels are drawn.

- Source: `prototype/assets/characters/limb_puzzle.json`
- Schema: `limb_puzzle_v1`; 64 x 64 cells, eight walk frames in the order
  `contact_a`, `down_a`, `passing_a`, `up_a`, `contact_b`, `down_b`,
  `passing_b`, `up_b`.
- Every frame stores `left_hand`, `right_hand`, `left_foot`, and `right_foot`
  as independent rectangles with `x`, `y`, `w`, `h`, `angle`, and `z_order`.
- The current approved occlusion relationship is fixed: `left_hand` and
  `left_foot` use `z_order: 9` (behind torso), torso uses `z_order: 10`, and
  `right_hand` and `right_foot` use `z_order: 11` (in front of torso).
- The rectangle positions and layer order are mandatory pose input. A body
  generation must render all four limbs from this contract; it must not hide a
  rear limb merely because the body is right-facing. Pixel-level registration
  may be refined, but the front/back relationship must not be inferred anew.

`tools/render_limb_puzzle_guide.py` renders this contract as a 2 x 4 layout
guide, and `prototype/preview/limb_puzzle.html` is the interactive
editor/exporter for this data.

### Animation Specification

- Direction set: front, right, back, left.
- First cycle: eight frames per direction.
- Frame order: left contact, passing, right contact, passing.
- Motion: small readable leg stride, opposite arm swing, restrained body bob, and a stable head anchor.
- Layout: one 4 x 8 sheet per presentation variant; rows are directions and columns are frames.
- Base content: no hair, ears, eyes, nose, mouth, clothing, underwear, accessories, or anatomical detail.
- Runtime composition: shared `Torso`, `Arms`, `LowerBody`, and `Feet` layers, plus a male or female blank-head layer. Female blush remains a separate optional face overlay.

### Execution Steps

1. Use the verified RGS eight-frame cycle as a pose and timing reference.
2. Redraw a male-presenting QQTang-style body for the eight phases while preserving shared frame bounds, baseline, head anchor, and collision footprint.
3. Validate the right-facing body in hidden Godot capture before creating the mirrored left-facing body.
4. Draw front and back cycles separately, then attach the existing head/ear anchors and validate the complete four-direction loop.
5. Only after the base cycle is accepted should hair, clothing, and randomization consume its slots.

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
- Suggested layers: `Feet`, `LowerBody`, `Arms`, `Torso`, `Ear`, `Head`, `Face`, `Hair`, `Clothing`, and optional `Accessory`.
- The reference BomboAdvanture assets use per-component walk textures. The prototype keeps eight stronger keyframes and applies one synchronized frame index to every layer.
- Head motion currently uses a fixed shared anchor; source-frame registration must be stable before adding any bob or clothing offsets.
- One controller stores `direction` and `walk_frame`, then applies the same `frame_coords` to every layer. This prevents random layers from drifting out of sync.
- Use `AnimatedSprite2D` with `SpriteFrames` when a character is already flattened into a single composite animation.

This layered `Sprite2D` approach is preferred for the planned random face, hair, and clothing system. Godot 4.6 supports sprite-sheet regions and frame coordinates on `Sprite2D`, while `AnimatedSprite2D` is better suited to a preassembled frame list.

### Asset Handoff Rule

The source walk sheets are reference sheets, not runtime-ready atlases: they contain a neutral background and guide grid. The processor isolates each cell, removes the guide/background, preserves one fixed registration box per direction, and exports layer-specific sheets before Godot import.

Recommended animation names are `idle_front`, `idle_right`, `idle_back`, `idle_left`, `walk_front`, `walk_right`, `walk_back`, and `walk_left`. The current runtime walk cycle uses eight frames per `walk_*` animation. The RGS reference is loaded only with `--rgs-walk-reference` in the silent test/capture pipeline.

## Minimal Prototype Status

The current runtime processing pass is complete for the QQTang-style neutral layers:

- The generated 4 x 8 sheets are split into 64 x 64 runtime cells with a 52-pixel subject envelope and a shared foot baseline.
- Magenta background was removed with local image processing; adjacent neutral layers overlap slightly at seams to prevent gaps.
- Transparent `Torso`, `Arms`, `LowerBody`, `Feet`, male-head, and female-head atlases, individual frames, and a JSON manifest were created under `prototype/assets/characters/chibi/`.
- The generated `chibi_compact` variant is kept beside the default assets for comparison; it is selected only with the `--compact` test argument.
- `prototype/` contains a UI-free Godot test project with movement, collision walls, eight-frame four-direction walk animation, and a simplified bomb fuse/blast feedback.
- The same prototype can select the female base with the `--female` command-line argument.

### Silent Verification

The Godot 4.6.2 console executable can be selected from `-GodotPath`, the `GODOT_BIN`/`GODOT_PATH` environment variable, `godot`/`godot4` on `PATH`, or the legacy sibling directory `Godot-4.6.2`. It is used without opening the editor UI.

Verified commands:

- headless project import: passed;
- male smoke test: `SMOKE_TEST_PASS`;
- female smoke test: `SMOKE_TEST_PASS`;
- two-second headless main-scene launch: passed.

The current prototype validates the movement and modular asset handoff path,
the deterministic face/ear layer, and the isolated RGS walk reference. It is not
yet the production character system and does not include random hair or clothing.

### Prototype Iteration 1 Fixes

- Corrected the generated side-view row mapping so left and right movement face the expected direction.
- Switched runtime playback to isolated 64 x 64 frame PNGs, preventing adjacent-frame bleed and the stray head fragment visible when moving upward.
- Replaced the small-head source with a QQTang-style oversized head, removed ears from every directional view, and split the runtime into four neutral body slots plus male/female head layers.
- Confirmed that the walk timer advances the actual texture frame while movement continues.
- Reprocessed transparent frames with edge-color extrusion to reduce filtered halos and particle-like edge noise.

### Prototype Iteration 2 Registration Pass

- Replaced per-frame foreground cropping and resizing with one fixed union registration box per direction, shared by every visual layer.
- Tightened magenta removal so dark-magenta background pixels cannot become one-frame foreground noise.
- Removed runtime head bob until the source poses and seam anchors are stable.
- Preserved the current walk phase when movement stops, preventing a visible reset to frame zero.
- Added `tools/validate_chibi_frames.py` to check 64 x 64 frame size, layer seams, and foot baseline before headless tests; it validates 192 frames across six layers.

### Prototype Iteration 3 Outfit-Ready Layers

- Split the neutral mannequin into `Torso`, `Arms`, `LowerBody`, and `Feet` slots with deliberate seam overlap.
- Kept the old `body` and `leg` files as legacy outputs; the runtime now uses the five-layer stack so future clothing can replace or cover individual regions.
- Added `-Compact` to the headless runner and GIF capture so candidate walk sources can be evaluated without changing the default runtime assets.

### Automated Visual Capture

`tools/capture_walk_gif.ps1` runs `prototype/tests/capture_test.gd` with internal W/A/S/D key events, captures the rendered viewport at 12 FPS, and uses the local Pillow tool environment to produce a GIF. Add `-RgsWalkReference` to capture `movement_rgs_reference.gif`. Godot is launched as a hidden process with the normal OpenGL renderer because Godot's dummy `--headless` renderer has no readable viewport texture on this machine. The test still runs without presenting an editor or game window.

`tools/run_headless_tests.ps1` runs the male smoke test and optionally the female smoke test with `--headless`; add `-Compact` to test the compact asset variant. Set `$env:GODOT_BIN` (or `$env:GODOT_PATH`) or pass `-GodotPath` when Godot is installed in a different directory.

`tools/process_face_variants.py` converts the image-generated face and ear
reference sheets into transparent 64 x 64 layers and writes
`prototype/assets/characters/faces/face_manifest.json`. Use
`-AppearanceSeed 12345` with the headless runner to verify a repeatable
appearance selection.

The random appearance test package is generated at each test startup under
`prototype/test_output/random_appearance/`. It contains composited 4 x 8
runtime frames and a manifest, and is ignored by Git. The package uses the same
seed passed to Godot, so the generated preview and the original movement/GIF
test exercise the same face, ears, and base layers.

The fixed fitting candidate is stored under
`prototype/assets/characters/base_features_v1/`. It is generated with
direction-aware 4 x 8 frames and per-frame registration against the existing
head alpha bounds. It is intentionally marked `randomization_ready: false`;
random variants should only consume it after the base movement GIF is accepted.

`tools/capture_walk_gif.ps1` resolves Python from `-PythonPath`, `$env:PYTHON_BIN`, PATH, or the local `.venv`/sibling fallback. Pillow is required for GIF conversion.
