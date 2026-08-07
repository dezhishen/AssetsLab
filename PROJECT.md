# AssetsLab — 数据驱动角色素材管线

数据驱动角色管线：3D 动作引擎 + 物种/预设 + CLI/HTTP 双入口 + Web 前端预览 + Godot demo。

## 类型声明

`assetslab/models.py` — Python TypedDict 类型声明，面向人类和 AI 的可读文档。
定义了 Species → Preset → Motion 三层数据模型及所有 API 响应类型。

## 统一 Api（CLI 与 HTTP 共享同一套接口，避免两侧漂移）

- `assetslab/interfaces.py` — `Api`（Protocol，`@runtime_checkable`）：统一接口契约。**新增任何操作必须先在此声明**，两侧（CLI/HTTP）自动一致。
- `assetslab/api.py` — `ApiService`：唯一实现（组合物种 + 预设 + 3D 渲染）。`make_api()` 返回时 `assert isinstance(service, Api)` 运行时硬约束。
- `assetslab/server.py` — HTTP handler 只依赖 `Api`（薄路由层，无业务/渲染逻辑）。
- `assetslab/cli.py` — CLI 直接实例化 `ApiService`（`python -m assetslab.cli`，不启动 server）。

## 存储结构

```
assetslab/
  api.py / interfaces.py / cli.py / server.py   ← 统一 Api + HTTP + CLI
  species.py / presets.py / models.py / motion.py
  skeleton3d.py / render.py                      ← 3D 引擎 + 绘制原语
  species/                    ← 物种（文件夹式，细颗粒度管理）
    human/
      skeleton.json           ← 骨骼拓扑：关节、骨骼、链、参数链、约束
      preset_schema.json      ← 预设 schema（随骨架自动派生）
      default.json            ← 默认姿态/体型（positions_3d 按真实 CMU 重建）
      actions3d/walk3d.json   ← 3D 动作（FK 关节旋转，真实 CMU 数据）
  presets/                    ← 预设（物种实例：体型 + 动作幅度）
    <preset_id>.json          ← {species, body, actions}（schema 由物种派生，不落盘）
  web/                        ← Vue 3 前端（物种 / 预设 独立入口）
scripts/
  mocap/                      ← CMU 动捕工具链（bvh_parser / rebuild_skeleton_cmu / ...）
  verify_motions3d.py         ← 3D 动作验证（8 项检查，数据驱动）
prototype/                    ← Godot 4.7 demo（保留）
```

## API（HTTP：handler 薄路由 → ApiService）

| 端点 | 说明 |
|---|---|
| `GET /api/species` | 物种列表 |
| `GET /api/species/<id>` | 物种详情（骨架 + 动作） |
| `POST/PUT/DELETE /api/species...` | 物种 CRUD + `preset_schema` / `default` / `actions` |
| `GET /api/presets` | 预设列表 |
| `GET /api/presets/new?species=` | 新建空白表单（含 schema） |
| `GET/POST/PUT/DELETE /api/presets...` | 预设 CRUD |
| `GET /api/motions3d` | 跨物种动作列表 |
| `GET /api/skeleton3d/<id>?yaw=45` | 3D 骨架 PNG（支持体型参数） |
| `GET /api/motion3d/<id>?gif=1` | 3D 动作 PNG / GIF / frames |
| `GET /api/preset3d/<id>` | 预设渲染（骨架/动作，应用体型 + 动作参数） |
| `GET /api/preset3d/live?...` | 实时预览（未保存的 body/actions） |

**3D 相机参数**（轨道相机：绕模型中心，从空间一点看模型）：
- `yaw` 水平角（0-360：0=front，90=side，180=back）；`pitch` 俯仰角（-60~60）
- `dist` 相机距离（200-1500）；`zoom` 缩放倍率（0.5-2）
- 前端：快捷视角按钮（常驻）+「相机」面板（细调，收纳）+ **预览图拖拽旋转**

## CLI（与 HTTP 同级，共用同一套 Api）

```bash
.venv/bin/python -m assetslab.cli species list
.venv/bin/python -m assetslab.cli species schema human
.venv/bin/python -m assetslab.cli preset new human
.venv/bin/python -m assetslab.cli preset create --json '{"preset_id":"m","species":"human","title":"M","body":{"head_scale":1.2}}'
.venv/bin/python -m assetslab.cli render skeleton human --out skel.png --yaw 45 --body head_scale=1.2
.venv/bin/python -m assetslab.cli render motion walk3d --gif --out walk.gif
.venv/bin/python -m assetslab.cli render preset m --action walk3d --gif --out walk.gif
```

## 启动

**生产（Python 直接服务 dist 静态 + API）**
```bash
cd assetslab/web && pnpm install && pnpm run build
python assetslab/server.py --port 8765
```

**开发（热更新，前后端分离）**
- 终端 1 — 后端 API（`--dev` 追加 CORS 头）：`.venv/bin/python assetslab/server.py --dev --port 8765`
- 终端 2 — 前端 Vite dev（proxy `/api` `/run` → 8765）：`cd assetslab/web && pnpm run dev`（http://localhost:5173）
  - 也可在 web 目录用 `pnpm run dev:api` 起后端；后端端口可用 `API_TARGET` 环境变量覆盖 proxy 目标

## 3D 架构（FK 关节旋转 + 真实动捕）

```
动作 walk3d.json（fk3d.rotations3d：全关节每帧真实旋转 table + root3d 根位移）
   + 骨架 skeleton.json（fk_tree/fk_local 骨向量）+ default.json（positions_3d 体型）
        ↓ build_skeleton_3d()
3D 骨架 {joint: [x,y,z]}
        ↓ pose_3d()  →  FK 正向运动学（父累积旋转）+ 3D IK + 刚性传播
3D 姿势
        ↓ project3d()（yaw/pitch/dist/zoom 透视）
屏幕坐标 → render_pose() → PNG / GIF
```

- **骨骼与 walk 按真实 CMU 动捕重建**（subject16, `16_15.bvh`）：骨长比例精确一致、全关节旋转照搬
- `skeleton3d.py`：FK（solve_fk3d）、3D 两骨 IK（pole 定弯曲）、渲染、自动适配
- `motion.py`：信号 DSL（table / param / phase / ...）
- 前端：物种（骨骼/动作管理）与预设（调体型/动作幅度）**独立入口**；3D 相机（轨道 + 面板 + 拖拽）；动作预览（播放 + 导出 GIF）

## 架构约束（强制 — 禁止硬编码，数据驱动）

> 本约定为强制约束。任何代码新增/修改都必须遵守，违者视为架构违规。

**核心原则：数据在 JSON，逻辑在引擎，参数化渲染。**
- 关节名 / 解剖方向 / 路径 / 数值常量一律从 JSON（骨架 `constraints`、default `canvas`、派生 schema）读取，**禁止硬编码**
- 渲染 = 读取（骨架 JSON + 动作 JSON + 动作参数 + 体型参数 + 相机参数）→ 计算 → 输出；引擎不产生新数据语义，缺字段回退/报错，**不得在代码里补默认人类值**

**JSON 多层（数据归属）**
| 层 | 数据 | 存放 |
|----|------|------|
| 物种 skeleton.json | 拓扑、`fk_tree`、`bones_3d`、约束（`joint_direction`/`rigid_chains`/`symmetry3d`/...） | `species/<id>/skeleton.json` |
| 默认 default.json | `positions_3d`（3D 体型坐标）、`canvas`（画布/地面/中心） | `species/<id>/default.json` |
| 预设 | 值（`body` 体型 + `actions` 动作幅度），schema 由物种派生 | `presets/<id>.json` |
| 动作 action | `fk3d`（关节旋转）、`root3d`、`ik3d`、`signals`、`params` | `species/<id>/actions3d/<id>.json` |

**验证也数据驱动**：`verify_motions3d.py` 的检查项（对称对、顺拐对、刚性跟随、脚着地、肘角）全部从骨架 `constraints` 读取，禁止硬编码关节名。
