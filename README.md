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
| `tools/` | Toolchain: asset build / process / validate (Python), headless tests & captures (PowerShell) |
| `third_party/` | Open-source reference assets (CC0 RGS modular character, Female Adventurer walk reference) — pose-timing reference only, not the final art style |
| `PROJECT.md` | Project charter: development status, roadmap, review principles |
| `references/` | Design reference images: mannequin sheets, front character anchors |
| `prototype/assets/characters/walk_base/` | Authoritative 4-direction walk base source sheets |
| `workflow/` | Workflow engine SDK: declarative definitions + CLI scheduling |
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
├── tools/                     # Build / validate / capture / preview scripts
├── workflow/                  # Workflow engine SDK + declarative definitions
├── run/                       # Per-instance workflow state (git ignored, generated)
└── third_party/               # Open-source reference assets
```

## Quick start

### Prerequisites

- **Godot 4.6.2**: automation scripts require a `_console.exe` headless build (`--headless`). Resolution order: `-GodotPath` → `GODOT_BIN`/`GODOT_PATH` → `godot`/`godot4` on `PATH` → adjacent `Godot-4.6.2` directory.
- **Python 3 + Pillow**: required for asset processing and GIF compositing. Resolution order: `-PythonPath` → `PYTHON_BIN` → `PATH` → local `.venv`/adjacent directory.
- PowerShell scripts target Windows; the cross-platform Python tools run directly on Linux/macOS.

All commands below are executed from the **repository root**.

> **Cross-platform CLI (recommended):** `tools/assetslab.py` mirrors every
> PowerShell script below and runs on Windows, Linux and macOS:
> `doctor`, `test`, `capture-walk`, `stage <view> <stage>`, `preview`,
> `publish`, and `run-script`. It accepts the same flags
> (`--female`, `--compact`, `--rebuild-head`, `--appearance-seed`, ...) and
> resolves Godot via `--godot` / `GODOT_BIN` / `GODOT_PATH` / `PATH` / an
> adjacent `Godot-4.6.2` install. The PowerShell scripts below remain the
> canonical Windows entry points.

### 1. Headless smoke test

```powershell
# Generate random appearance package -> validate assets -> launch Godot smoke test
.\tools\run_headless_tests.ps1

# Common options
.\tools\run_headless_tests.ps1 -Female                                  # female base
.\tools\run_headless_tests.ps1 -RebuildHead -VerticalCandidate          # calibrated head + vertical candidate
.\tools\run_headless_tests.ps1 -AppearanceSeed 20260730                 # fixed seed
.\tools\run_headless_tests.ps1 -GodotPath 'E:\Path\To\godot_console.exe' # custom Godot
```

**Cross-platform equivalent:**

```bash
python3 tools/assetslab.py test
python3 tools/assetslab.py test --female --rebuild-head --vertical-candidate
python3 tools/assetslab.py test --appearance-seed 20260730
python3 tools/assetslab.py test --godot /path/to/godot
```

### 2. Capture walk animation GIF

```powershell
.\tools\capture_walk_gif.ps1                       # four-direction walk GIF -> prototype/test_output/
.\tools\capture_walk_gif.ps1 -RebuildHead -VerticalCandidate -VerticalOnly  # vertical candidate only
.\tools\capture_walk_gif.ps1 -MilestoneBodyRight -RightOnly                 # right-facing milestone only
```

**Cross-platform equivalent:**

```bash
python3 tools/assetslab.py capture-walk
python3 tools/assetslab.py capture-walk --rebuild-head --vertical-candidate --vertical-only
python3 tools/assetslab.py capture-walk --milestone-body-right --right-only
```

### 3. Skeleton pipeline (stage advancement)

```powershell
.\tools\capture_front_skeleton_stage.ps1    # front static skeleton
.\tools\capture_front_leg_cycle_stage.ps1   # front leg loop
.\tools\capture_front_pelvis_bob_stage.ps1  # front pelvis bob
.\tools\capture_front_arm_swing_stage.ps1   # front arm swing
# side / back have equivalent scripts
```

**Cross-platform equivalent:**

```bash
python3 tools/assetslab.py stage front skeleton
python3 tools/assetslab.py stage front legs
python3 tools/assetslab.py stage front pelvis
python3 tools/assetslab.py stage front arms
python3 tools/assetslab.py stage back legs
```

Each stage writes to `prototype/test_output/skeleton_pipeline/` (PNG + GIF) and must pass visual review before the next stage begins.

### 4. Local preview

**Windows (one-click publish + start):**

```powershell
.\tools\serve_preview.ps1 -SnapshotName my_review   # publish snapshot and start LAN server
.\tools\stop_preview.ps1                             # stop the server
```

**Linux / cross-platform (start the static server directly):**

```bash
python3 tools/lan_preview_server.py --port 8765 --directory prototype/preview
# or, equivalently:
python3 tools/assetslab.py preview --port 8765
# open http://127.0.0.1:8765/  (server binds 0.0.0.0; LAN devices can use http://<host-ip>:8765/)
```

The preview page summarizes the skeleton pipeline stages, the current base, candidates, and GIFs; interactive calibration pages `/calibrate.html`, `/limb_calibrate.html`, and `/body_calibrate.html` are also served (calibration data is saved via API to `prototype/preview/calibration/`).

### 5. Asset build & processing

```bash
python tools/build_body_vertical_update.py   # rebuild front/back vertical walk candidate frames
# or: python3 tools/assetslab.py run-script build_body_vertical_update.py
python tools/recolor_body_palettes.py        # generate light/warm/deep skin variants (size & alpha preserved)
python tools/build_preview_assets.py         # rebuild preview asset set
python tools/publish_preview.py --name tag   # publish timestamped snapshot to preview/snapshots/
```

### 6. Workflow engine (AI / human scheduling)

`tools/workflow.py` drives the pipeline step-by-step with a persistent,
per-instance state under `run/workflows/<workflow_id>/`:

```bash
python tools/workflow.py list                                            # list instances
python tools/workflow.py new --definition default --id review-a          # create instance
python tools/workflow.py status --workflow review-a --json               # view state
python tools/workflow.py next --workflow review-a                        # recommended next action
python tools/workflow.py run --workflow review-a --action skeleton.front.legs --json
python tools/workflow.py approve --workflow review-a --action skeleton.front.legs --by ai --note "ok"
python tools/workflow.py reject --workflow review-a --action skeleton.front.legs --by human --note "redraw"
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
