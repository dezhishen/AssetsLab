# AssetsLab

A pixel-art character animation experiment built on **Godot 4.6.2**. The core work is a pipeline of **"skeleton-first validation, layered-atlas rendering, headless-test gating"** that produces a QQTang-style (oversized-head) character walk cycle across **four directions × eight frames**, plus a minimal playable slice as the runtime verification.

- Engine: Godot 4.6.2 (GL Compatibility renderer, suited for 2D pixels and cross-platform/headless automation)
- Directions: front / right / back / left, an 8-frame walk cycle per direction
- Runtime character: 7 stacked `Sprite2D` layers (Feet / LowerBody / Arms / Torso / Ear / Head / Face); head and face appearance are selected by a **deterministic seed**
- Minimal gameplay: move with WASD/arrow keys, place one short-fuse bomb with Space (its blast sends the player back to spawn)

## What's in the project

| Module | Description |
|---|---|
| `prototype/` | Godot 4.6.2 project: runtime scripts, layered assets, headless tests, browser preview pages |
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
├── prototype/                 # Godot 4.6.2 project
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

- **Godot 4.6.2**: automation scripts require a `_console.exe` headless build (`--headless`). Resolution order: `--godot` → `GODOT_BIN`/`GODOT_PATH` → `godot`/`godot4` on `PATH` → adjacent `Godot-4.6.2` directory.
- **Python 3 + Pillow**: required for asset processing and GIF compositing. Resolution order: `--python` → `PYTHON_BIN` → `PATH` → local `.venv`/adjacent directory.
- Everything is pure Python and cross-platform — no PowerShell or shell scripts are used.

All commands below are executed from the **repository root**.

> **CLI (unified entry):** `workflow/tools/assetslab.py` runs on Windows, Linux
> and macOS: `doctor`, `test`, `capture-walk`, `stage <view> <stage>`,
> `preview`, `publish`, and `run-script`. It accepts flags
> (`--female`, `--compact`, `--rebuild-head`, `--appearance-seed`, ...) and
> resolves Godot via `--godot` / `GODOT_BIN` / `GODOT_PATH` / `PATH` / an
> adjacent `Godot-4.6.2` install.

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
python -m workflow run --workflow review-a --action skeleton.front.legs --json
python -m workflow approve --workflow review-a --action skeleton.front.legs --by ai --note "ok"
python -m workflow reject --workflow review-a --action skeleton.front.legs --by human --note "redraw"
```

- CLI is the AI-facing scheduling channel: `--json` output is machine-readable
  and `outputs` returns absolute paths to local images.
- Web is the human-facing full channel: `http://<host>:8765/workflow.html`;
  images are served under `http://<host>:8765/run/workflows/<id>/steps/<action_id>/`.
- `workflow_id` / `action_id` run through CLI, Web and persistence; multiple
  instances can run in parallel, each persisted to its own JSON.

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
