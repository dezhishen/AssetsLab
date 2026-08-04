# AssetsLab

A pixel-art character animation experiment built on **Godot 4.7**. The core work is a pipeline of **"skeleton-first validation, layered-atlas rendering, headless-test gating"** that produces a QQTang-style (oversized-head) character walk cycle across **four directions × eight frames**, plus a minimal playable slice as the runtime verification.

- Engine: Godot 4.7 (GL Compatibility renderer, suited for 2D pixels and cross-platform/headless automation)
- Directions: front / right / back / left, an 8-frame walk cycle per direction
- Runtime character: 7 stacked `Sprite2D` layers (Feet / LowerBody / Arms / Torso / Ear / Head / Face); head and face appearance are selected by a **deterministic seed**
- Minimal gameplay: move with WASD/arrow keys, place one short-fuse bomb with Space (its blast sends the player back to spawn)

## What's in the project

| Module | Description |
|---|---|
| `prototype/` | Godot 4.7 project: runtime scripts, layered assets, headless tests, browser preview pages |
| `third_party/` | Open-source reference assets (CC0 RGS modular character, Female Adventurer walk reference) — pose-timing reference only, not the final art style |
| `PROJECT.md` | Project charter: development status, roadmap, review principles |
| `references/` | Design reference images: mannequin sheets, front character anchors |
| `prototype/assets/characters/walk_base/` | Authoritative 4-direction walk base source sheets |
| `workflow/` | Workflow engine: SDK + tools (assetslab, build, validate) + definitions |
| `run/` | Per-instance workflow state (git ignored): state.json + step image outputs |

### Core methodology: skeleton-first walk pipeline

Pose timing and layering rules are first validated with **procedurally drawn skeletons** in Godot `_draw()`; only after they pass are the pixel assets redrawn against them. Each direction advances through stages, and every stage has its own script + headless capture + built-in assertions:

1. **Static base skeleton**: symmetry and shared foot baseline
2. **Eight-frame leg loop**: alternating contact/passing poses (F0/F4 are contact frames; left leg is front for the first half cycle, right for the second)
3. **Pelvis vertical bob**: ≤6px peak-to-peak only
4. **Opposite arm swing**: counterphased to the corresponding leg; hands stay inside the center axis

Progress: **front and side have passed all 4 stages; back is paused after the eight-frame leg loop**. Stage artifacts and gates are recorded in the manifest JSON under `prototype/assets/characters/generated/skeleton_walk_pipeline_v1/`.

## Directory structure

```text
assets-lab/
├── PROJECT.md                 # Project charter
├── README.md                  # This file (English)
├── README_ZH.md               # Chinese version of this README
├── references/                # Design reference images (mannequin sheets, anchors)
├── prototype/                 # Godot 4.7 project
│   ├── project.godot
│   ├── main.tscn              # Main scene (player + arena + walls)
│   ├── scripts/               # Runtime + skeleton pipeline stage scripts
│   ├── assets/characters/     # Layered assets (chibi, faces, generated candidates, etc.)
│   ├── tests/                 # Headless validation tests (smoke_test, etc.)
│   ├── preview/               # Browser preview pages + interactive calibration pages
│   └── README.md              # Detailed prototype run instructions
├── workflow/                  # Workflow engine: SDK + tools + definitions
│   ├── tools/                 # Executable scripts (assetslab, capture, build, validate)
│   └── definitions/           # Declarative workflow definitions
├── run/                       # Per-instance workflow state (git ignored, generated)
└── third_party/               # Open-source reference assets
```

## Quick start

### Prerequisites

- **Godot 4.7**: automation scripts require a `_console.exe` headless build (`--headless`). Resolution order: `--godot` → `GODOT_BIN`/`GODOT_PATH` → `godot`/`godot4` on `PATH` → adjacent `Godot-4.7` directory.
- **Python 3 + Pillow** (via a virtual environment): required for asset processing and GIF compositing. Resolution order: `--python` → `PYTHON_BIN` → local `.venv` → `PATH`.
- Everything is pure Python and cross-platform — no PowerShell or shell scripts are used.

### Virtual environment (recommended)

All Python tooling runs from `.venv/` so dependencies stay isolated; the
resolvers prefer it automatically.

```bash
# create once
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# optional: activate so `python` points at the venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# recommended: run with the venv interpreter (no activation needed)
.venv/bin/python workflow/tools/assetslab.py doctor
.venv/bin/python -m workflow list
```

Windows uses `.venv\Scripts\python.exe`. `requirements.txt` pins the Python
dependencies (Pillow).

All commands below are executed from the **repository root**.

> **CLI (unified entry):** `workflow/tools/assetslab.py` runs on Windows, Linux
> and macOS: `doctor`, `test`, `capture-walk`, `stage <view> <stage>`,
> `preview`, `publish`, and `run-script`. It accepts flags
> (`--female`, `--compact`, `--rebuild-head`, `--appearance-seed`, ...) and
> resolves Godot via `--godot` / `GODOT_BIN` / `GODOT_PATH` / `PATH` / an
> adjacent `Godot-4.7` install.

### 1. Headless smoke test

```bash
# Generate random appearance package -> validate assets -> launch Godot smoke test
python workflow/tools/assetslab.py test

# Common options
python workflow/tools/assetslab.py test --female                                  # female base
python workflow/tools/assetslab.py test --rebuild-head --vertical-candidate          # calibrated head + vertical candidate
python workflow/tools/assetslab.py test --appearance-seed 20260730                 # fixed seed
python workflow/tools/assetslab.py test --godot 'E:\Path\To\godot_console.exe' # custom Godot
```

**Cross-platform equivalent:**

```bash
python3 workflow/tools/assetslab.py test
python3 workflow/tools/assetslab.py test --female --rebuild-head --vertical-candidate
python3 workflow/tools/assetslab.py test --appearance-seed 20260730
python3 workflow/tools/assetslab.py test --godot /path/to/godot
```

### 2. Capture walk animation GIF

```bash
python workflow/tools/assetslab.py capture-walk                       # four-direction walk GIF -> prototype/test_output/
python workflow/tools/assetslab.py capture-walk --rebuild-head --vertical-candidate --vertical-only  # vertical candidate only
python workflow/tools/assetslab.py capture-walk --milestone-body-right --right-only                 # right-facing milestone only
```

**Cross-platform equivalent:**

```bash
python3 workflow/tools/assetslab.py capture-walk
python3 workflow/tools/assetslab.py capture-walk --rebuild-head --vertical-candidate --vertical-only
python3 workflow/tools/assetslab.py capture-walk --milestone-body-right --right-only
```

### 3. Skeleton pipeline (stage advancement)

```bash
python workflow/tools/assetslab.py stage front skeleton    # front static skeleton
python workflow/tools/assetslab.py stage front legs   # front leg loop
python workflow/tools/assetslab.py stage front pelvis  # front pelvis bob
python workflow/tools/assetslab.py stage front arms   # front arm swing
# side / back have equivalent scripts
```

**Cross-platform equivalent:**

```bash
python3 workflow/tools/assetslab.py stage front skeleton
python3 workflow/tools/assetslab.py stage front legs
python3 workflow/tools/assetslab.py stage front pelvis
python3 workflow/tools/assetslab.py stage front arms
python3 workflow/tools/assetslab.py stage back legs
```

Each stage writes to `prototype/test_output/skeleton_pipeline/` (PNG + GIF) and must pass visual review before the next stage begins.

### 4. Local preview

**Windows (one-click publish + start):**

```bash
python workflow/tools/lan_preview_server.py --port 8765 --directory prototype/preview --name my_review   # publish snapshot and start LAN server
# stop: kill the lan_preview_server process                             # stop the server
```

**Linux / cross-platform (start the static server directly):**

```bash
python3 workflow/tools/lan_preview_server.py --port 8765 --directory prototype/preview
# or, equivalently:
python3 workflow/tools/assetslab.py preview --port 8765
# open http://127.0.0.1:8765/  (server binds 0.0.0.0; LAN devices can use http://<host-ip>:8765/)
```

The preview page summarizes the skeleton pipeline stages, the current base, candidates, and GIFs; interactive calibration pages `/calibrate.html`, `/limb_calibrate.html`, and `/body_calibrate.html` are also served (calibration data is saved via API to `prototype/preview/calibration/`).

### 5. Asset build & processing

```bash
python workflow/tools/build_body_vertical_update.py   # rebuild front/back vertical walk candidate frames
# or: python3 workflow/tools/assetslab.py run-script build_body_vertical_update.py
python workflow/tools/recolor_body_palettes.py        # generate light/warm/deep skin variants (size & alpha preserved)
python workflow/tools/build_preview_assets.py         # rebuild preview asset set
python workflow/tools/publish_preview.py --name tag   # publish timestamped snapshot to preview/snapshots/
```

### 6. Workflow engine (AI / human scheduling)

`-m workflow` drives the pipeline step-by-step with a persistent,
per-instance state under `run/workflows/<workflow_id>/`:

```bash
python -m workflow list                                            # list instances
python -m workflow new --definition default --id review-a          # create instance
python -m workflow status --workflow review-a --json               # view state
python -m workflow next --workflow review-a                        # recommended next action
python -m workflow run --workflow review-a --action skeleton.front --json
python -m workflow approve --workflow review-a --action skeleton.front --by ai --note "ok"
python -m workflow reject --workflow review-a --action skeleton.front --by human --note "redraw"
```

**Parameterized actions** — every action can declare tunable knobs in the
definition (e.g. `stride` / `pelvis_bob` / `arm_swing`), and a run can override
any of them; the used values are recorded in the action state for review:

```bash
python -m workflow run --workflow review-a --action skeleton.front --param stride=1.2 --param pelvis_bob=1.5 --json
```

**Style templates** — instead of starting from neutral knobs (stride=1.0),
pick an industry-style default set when creating an instance
(`--template realistic|cartoon|bouncy|heavy|light`). The template values become
the instance's default knobs (still overridable per run with `--param`); the
Web console offers the same templates when creating an instance and pre-fills
the wizard's parameter sliders with them.

```bash
python -m workflow new --definition default --id hero --template bouncy
python -m workflow run --workflow hero --action skeleton.front              # uses bouncy defaults
python -m workflow run --workflow hero --action skeleton.front --param stride=1.5   # override one knob
```

**Motion / body separation** — motion knobs (`stride`/`pelvis_bob`/`arm_swing`)
describe *how* the character moves and belong to a single action; **body
proportions** (arm_length/leg_length/torso_length/shoulder_width/head_scale/
height) describe *what the character looks like* and belong to the whole
instance (`state.body`), shared by front/side/back so all views stay
consistent for the same character. Pick a body template at creation with
`--body-template standard|chibi|tall|stocky`; `set-body` persists the
character, `run --body` overrides for one run:

```bash
python -m workflow new --definition default --id hero --template bouncy --body-template chibi
python -m workflow set-body --workflow hero --body head_scale=1.4
python -m workflow run --workflow hero --action skeleton.front --body height=1.1
```

- CLI is the AI-facing scheduling channel: `--json` output is machine-readable
  and `outputs` returns absolute paths to local images. The CLI drives the
  workflow SDK (`workflow.runner`) directly and does **not** depend on the
  Web server — you can run the whole schedule without starting any service.
- Web is the human-facing full channel: `http://<host>:8765/workflow.html`;
  images are served under `http://<host>:8765/run/workflows/<id>/steps/<action_id>/`.
  The CLI and the Web API are **two peer adapters over the same SDK** — the
  web server also calls `workflow.runner` in-process (it no longer shells out
  to the CLI), so neither depends on the other.
  Actions with tunable params open a parameter dialog before running (drag
  stride/pelvis-bob/arm-swing, then run), so a human actually tunes the pose
  instead of only clicking approve.
- **Step wizard**: `http://<host>:8765/flow.html?id=<workflow_id>` renders one
  step at a time (stepper + prev/next navigation, like an installer). Each step
  shows its params, output and review buttons; clicking an instance in
  `workflow.html` opens the wizard. First-open lands on a passed-but-unreviewed
  step (approve backlog first), otherwise the recommended next action.
- `workflow_id` / `action_id` run through CLI, Web and persistence; multiple
  instances can run in parallel, each persisted to its own JSON.

## Preview rendering (pure Python)

Skeleton pipeline previews are rendered with Pillow
(`workflow/tools/render_skeleton_preview.py`) — no Godot needed. Pose is
parameterized so AI can improve the walk directly:

```bash
python workflow/tools/assetslab.py stage front legs --renderer python --stride 1.2 --pelvis-bob 1.0 --arm-swing 1.1
python workflow/tools/render_skeleton_preview.py --view side --stage arms --arm-swing 1.5
```

- `--stride` leg swing amplitude · `--pelvis-bob` pelvis bob · `--arm-swing` arm swing.
- The workflow's skeleton actions already run `--renderer python`; Godot's
  headless capture stays available as `--renderer godot` for consistency checks.

### Data-driven motion presets (pose library)

Instead of hard-coded pose functions, animation cycles are declarative JSON
presets under `workflow/motions/` (`walk`, `run`, `idle`, `jump`). A preset
describes waveform **signals** + per-joint **offsets** relative to a shared
static base; the engine (`workflow/tools/motion.py`) samples them into frames.
Adding an animation is a new JSON file — no renderer changes.

```bash
python workflow/tools/assetslab.py motion list                          # list presets
python workflow/tools/assetslab.py motion info run                      # params & IK groups
python workflow/tools/assetslab.py motion render run --view front --stage legs --ik
python workflow/tools/assetslab.py motion check                         # walk == built-in poses
python workflow/tools/assetslab.py stage side arms --renderer python --motion run --ik
```

- `walk` is the reference preset: `motion check` and a pixel comparison prove
  it matches the Godot-consistent built-in poses exactly (all views/stages).
- **Head motion**: `head`/`neck` follow the pelvis bob at half amplitude, and
  sway forward/back on the side view — the classic counter-animation so the
  head is never locked (walk/run bob, idle breathing nod, jump follows the
  body lift).
- **Skeleton hierarchy (root-driven)**: joints form a rigid torso chain
  (pelvis → neck/head + shoulders/arms). Each motion declares a `root` — the
  pelvis translate (bob / jump lift / lean) — and every torso joint inherits
  it at a per-joint ratio (`base.json` → `torso`): shoulders/arms 1.0 (rigid),
  knees 0.5 (damped), head 0.5 (stable line of sight). A jump now lifts the
  shoulders/arms with the pelvis automatically, instead of patching each joint.
- **Two-bone IK** (`--ik`; presets declare `ik` groups) keeps leg lengths
  constant at large strides, and "foot-plant" locks an unreachable foot back
  onto the reachable radius — used by `run` / `jump`.
- **Body proportions** — the static base is tunable too: `arm_length`,
  `leg_length`, `torso_length`, `shoulder_width`, `head_scale`, `height`
  (each 1.0 = reference). They scale each bone segment around its anchor
  (e.g. `head_scale` grows the head from the neck, `leg_length` lengthens the
  thighs with feet planted), so the same motion presets drive any body shape.
  In the workflow these are a **character-level** property (instance `body`,
  shared by front/side/back so all views stay consistent): each step tunes
  only motion knobs, while the body is adjusted in the wizard's 「角色体型」
  panel or via `set-body`/`--body`. The low-level renderer still exposes
  `--proportion-*`:

  ```bash
  python workflow/tools/assetslab.py motion render walk --view front --stage arms \
      --proportion-head-scale 1.4 --proportion-arm-length 1.3
  ```
- **Cross-motion blending**: `--blend run --blend-t 0.5` interpolates joints
  for a parameterized walk↔run transition.
- **Web**: the workflow console `/workflow.html` gained a *Motion Studio*
  panel — pick a preset/view/stage, drag stride/pelvis-bob/arm-swing, toggle
  IK, blend between motions, and render the loop in the browser via
  `POST /api/motions/<id>/render`.

## Artifacts & Godot demo

The final workflow action `export.artifacts` builds a Godot-ready package under
`dist/<workflow_id>/` (pure Python, no Godot needed):

```text
dist/<workflow_id>/
├── atlas/                      # layered 4×8 frames (feet/lower_body/arms/torso/head_base/ear/face)
├── runtime_manifest.json       # directions, layer order, head_anchor_offsets
├── character_walk_4way.gif     # Pillow-composited preview
└── README.md
```

Run the minimal interactive demo against the artifact:

```bash
godot --path prototype -- --artifacts dist/<workflow_id>
```

The demo keeps interactive movement (WASD/arrows) and bomb placement (Space).

## Output locations

| Artifact | Path | Git |
|---|---|---|
| Test / capture output | `prototype/test_output/` | ignored |
| Random appearance package | `prototype/test_output/random_appearance/` | ignored |
| Preview snapshots | `prototype/preview/snapshots/` | ignored |
| Runtime layered assets | `prototype/assets/characters/chibi/` | tracked |
| Generated candidates / skeleton pipeline | `prototype/assets/characters/generated/` | tracked |

## Current status & roadmap

- **Done**: complete front/side skeleton cycle (skeleton → legs → pelvis → arms); back eight-frame leg loop; calibrated head runtime; deterministic seeded appearance.
- **In progress**: back pelvis/arms → verified left mirror → four-direction anchor review → body blocks and calibrated head attachment.
- **Todo**: male/female variants, modular random face/hair/clothing layers, merging the vertical walk candidate into the runtime, diagonal directions (deferred until the four-direction contract is stable).
- **Archived**: rejected AI body/head experiments, Skeleton2D experiments, etc. are kept on the `history0731` branch for audit and are not part of the main-line asset set.

## Related documentation

- [`PROJECT.md`](PROJECT.md) — project charter: development status, candidate reviews, resource cleanup
- [`prototype/README.md`](prototype/README.md) — detailed prototype technical notes and all commands
- [`prototype/preview/README.md`](prototype/preview/README.md) — preview page build & publish notes
- [`README_ZH.md`](README_ZH.md) — 中文版项目说明 (Chinese version of this README)
