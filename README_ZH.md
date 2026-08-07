# AssetsLab（中文说明）

数据驱动角色素材管线：**3D 动作引擎（CMU 动捕真实数据）+ 物种/预设 + CLI/HTTP 双入口 + Web 前端预览 + Godot demo**。

## 项目内容

- **3D 动作引擎**：骨骼拓扑（`skeleton.json`）+ FK 关节旋转驱动动作，任意视角（轨道相机）渲染 PNG / GIF。
- **真实动捕**：骨骼与 `walk3d` 完全按 **CMU MoCap（subject16, `16_15.bvh`）** 数据重建——骨长比例精确一致、全关节旋转照搬。
- **物种 / 预设**：物种定义骨骼拓扑与动作；预设是基于物种的实例（调体型 + 动作幅度）。前端独立入口，不同角色处理。
- **CLI / HTTP 同级**：共用同一套 `Api` 接口（`interfaces.Api` + `api.ApiService`），避免两侧漂移。
- **Web 前端**（Vue 3）：物种 / 预设独立入口；动作预览（播放 + 导出 GIF）；3D 相机（快捷按钮 + 收纳面板 + 拖拽旋转）。
- **Godot demo**：`prototype/`（Godot 4.7 工程）保留，作为运行时验证。

## 目录结构

```
assetslab/
  api.py / interfaces.py / cli.py / server.py   ← 统一 Api（CLI 与 HTTP 共用）+ 薄路由 + CLI
  species.py / presets.py / models.py / motion.py
  skeleton3d.py / render.py                      ← 3D 引擎（FK/IK/投影）+ 绘制
  species/human/                                 ← 物种：骨骼 + 默认体型 + 动作
    skeleton.json / preset_schema.json / default.json
    actions3d/walk3d.json                        ← 3D 动作（FK 旋转，真实 CMU 数据）
  presets/                                       ← 预设（物种实例：body 体型 + actions 动作幅度）
  web/                                           ← Vue 3 前端
scripts/
  mocap/                                         ← CMU 动捕工具链（BVH 解析 / 重建 / 验证）
  verify_motions3d.py                            ← 3D 动作验证（8 项检查，数据驱动）
prototype/                                       ← Godot 4.7 demo（保留）
```

## 快速开始

### 环境要求

- Python 3.11+（建议 `.venv/`，`Pillow==12.3.0`；纯 Python，无 numpy/scipy）
- Node.js + **pnpm**（前端）

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
cd assetslab/web && pnpm install
```

### 生产

```bash
cd assetslab/web && pnpm run build            # 构建前端 dist
cd ../.. && .venv/bin/python assetslab/server.py --port 8765   # 后端服务 dist + API
# 打开 http://localhost:8765
```

### 开发（热更新，前后端分离）

- 终端 1 — 后端 API（`--dev` 追加 CORS 头）：`.venv/bin/python assetslab/server.py --dev --port 8765`
- 终端 2 — 前端 Vite dev（proxy `/api` `/run` → 8765，即时热更新）：
  ```bash
  cd assetslab/web && pnpm run dev    # http://localhost:5173
  ```
  - 也可在 web 目录 `pnpm run dev:api` 起后端；后端端口可用 `API_TARGET` 覆盖 proxy 目标。

### CLI（不启动 server，与 HTTP 同级）

```bash
.venv/bin/python -m assetslab.cli species list
.venv/bin/python -m assetslab.cli preset new human
.venv/bin/python -m assetslab.cli render skeleton human --out skel.png --yaw 45 --body head_scale=1.2
.venv/bin/python -m assetslab.cli render motion walk3d --gif --out walk.gif
.venv/bin/python -m assetslab.cli render preset <id> --action walk3d --gif --out walk.gif
```

## 3D 架构（FK 关节旋转 + 真实动捕）

```
动作 walk3d.json（fk3d.rotations3d：全关节每帧真实旋转 table + root3d 根位移）
   + 骨架 skeleton.json（fk_tree/fk_local 骨向量）+ default.json（positions_3d 体型）
        ↓ build_skeleton_3d()
3D 骨架 {joint: [x,y,z]}
        ↓ pose_3d()  →  FK 正向运动学（父累积旋转）+ 3D IK + 刚性传播
3D 姿势
        ↓ project3d()（yaw/pitch/dist/zoom 透视）
2D 屏幕坐标 → render_pose() → PNG / GIF
```

- **骨骼与 walk 按真实 CMU 动捕重建**：骨长比例精确一致、全关节旋转照搬（`scripts/mocap/rebuild_skeleton_cmu.py`）。
- 3D 相机 = 轨道相机（绕模型中心）：`yaw/pitch/dist/zoom`；前端支持拖拽旋转 + 快捷按钮 + 收纳面板。
- 预设 = 基于物种的实例：**体型参数**（骨骼尺寸，schema 由骨架 `param_chains` 派生）+ **动作参数**（动作幅度，schema 由动作 JSON `params` 派生），界面按 schema 自动渲染。

## 当前状态与路线图

- ✅ 骨骼 + walk：真实 CMU 数据驱动，`verify_motions3d.py` 8 项全 PASS
- ✅ 统一 Api：CLI 与 HTTP 共享 `interfaces.Api`（硬约束）
- ✅ 预设系统：独立入口（前端 + CLI），schema 派生 + 实时预览
- ✅ Web 前端：动作预览（播放 + GIF 导出）、3D 轨道相机、dev 热更新
- 🔜 run / jump 等动作按 CMU 真实数据补全；Godot demo 接入 3D 动作

## 相关文档

- `PROJECT.md` — 当前架构与约束（强制数据驱动）
- `TODO.md` — 任务交接 / 待办
