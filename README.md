# AssetsLab

Data-driven character asset pipeline: **3D motion engine (real CMU MoCap data) + species/presets + CLI/HTTP dual entry + Web preview + Godot demo**.

## Highlights

- **3D motion engine**: skeleton topology (`skeleton.json`) + FK joint-rotation driven motions, rendered as PNG/GIF from any orbit-camera view.
- **Real MoCap**: skeleton and `walk3d` rebuilt entirely from **CMU MoCap (subject16, `16_15.bvh`)** — bone lengths match exactly, per-frame joint rotations copied verbatim.
- **Species / Presets**: species defines skeleton topology & motions; presets are species instances (tune body proportions + motion amplitude). Independent front-end entries for different roles.
- **CLI / HTTP share one `Api` interface** (`interfaces.Api` + `api.ApiService`) — hard constraint prevents the two sides from drifting.
- **Web front-end** (Vue 3): independent species / presets entries; motion preview (play + GIF export); orbit camera (quick buttons + collapsible panel + drag-to-rotate).
- **Godot demo**: `prototype/` (Godot 4.7) kept as runtime validation.

## Layout

```
assetslab/
  api.py / interfaces.py / cli.py / server.py   ← unified Api (CLI & HTTP) + thin router + CLI
  species.py / presets.py / models.py / motion.py
  skeleton3d.py / render.py                      ← 3D engine (FK/IK/projection) + drawing
  species/human/                                 ← species: skeleton + default body + motions
    skeleton.json / preset_schema.json / default.json
    actions3d/walk3d.json                        ← 3D motion (FK rotations, real CMU data)
  presets/                                       ← presets (species instances: body + actions)
  web/                                           ← Vue 3 front-end
scripts/
  mocap/                                         ← CMU MoCap toolchain (BVH parse / rebuild / verify)
  verify_motions3d.py                            ← 3D motion verification (8 checks, data-driven)
prototype/                                       ← Godot 4.7 demo (kept)
```

## Quick start

### Prerequisites

- Python 3.11+ (recommend `.venv/`, `Pillow==12.3.0`; pure Python, no numpy/scipy)
- Node.js + **pnpm** (front-end)

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
cd assetslab/web && pnpm install
```

### Production

```bash
cd assetslab/web && pnpm run build            # build front-end dist
cd ../.. && .venv/bin/python assetslab/server.py --port 8765   # serve dist + API
# open http://localhost:8765
```

### Development (hot reload, split front/back)

- Terminal 1 — backend API (`--dev` adds CORS): `.venv/bin/python assetslab/server.py --dev --port 8765`
- Terminal 2 — front-end Vite dev (proxy `/api` `/run` → 8765):
  ```bash
  cd assetslab/web && pnpm run dev    # http://localhost:5173
  ```
  - Or run the backend from the web dir with `pnpm run dev:api`; override proxy target via `API_TARGET`.

### CLI (no server, same Api layer as HTTP)

```bash
.venv/bin/python -m assetslab.cli species list
.venv/bin/python -m assetslab.cli preset new human
.venv/bin/python -m assetslab.cli render skeleton human --out skel.png --yaw 45 --body head_scale=1.2
.venv/bin/python -m assetslab.cli render motion walk3d --gif --out walk.gif
.venv/bin/python -m assetslab.cli render preset <id> --action walk3d --gif --out walk.gif
```

## 3D architecture (FK joint rotations + real MoCap)

```
action walk3d.json (fk3d.rotations3d: per-joint per-frame real rotation tables + root3d root offset)
   + skeleton skeleton.json (fk_tree/fk_local bone vectors) + default.json (positions_3d body)
        ↓ build_skeleton_3d()
3D skeleton {joint: [x,y,z]}
        ↓ pose_3d()  →  FK forward kinematics (parent-accumulated rotation) + 3D IK + rigid
3D pose
        ↓ project3d() (yaw/pitch/dist/zoom perspective)
2D screen coords → render_pose() → PNG / GIF
```

- **Skeleton & walk rebuilt from real CMU MoCap**: bone lengths match exactly, per-frame joint rotations copied verbatim (`scripts/mocap/rebuild_skeleton_cmu.py`).
- 3D camera = orbit camera around model center: `yaw/pitch/dist/zoom`; front-end supports drag-to-rotate, quick preset buttons, collapsible fine-tune panel.
- Preset = species instance: **body params** (bone sizes, schema derived from skeleton `param_chains`) + **action params** (amplitude, schema derived from action JSON `params`); UI renders panels from schema.

## Status & roadmap

- ✅ Skeleton + walk: real CMU data-driven, `verify_motions3d.py` 8 checks PASS
- ✅ Unified Api: CLI & HTTP share `interfaces.Api` (hard constraint)
- ✅ Presets: independent entry (front-end + CLI), schema-derived + live preview
- ✅ Web: motion preview (play + GIF export), orbit camera, dev hot reload
- 🔜 run/jump motions from real CMU data; wire Godot demo to 3D motions

## Docs

- `PROJECT.md` — current architecture & constraints (mandatory data-driven)
- `TODO.md` — handover / roadmap
