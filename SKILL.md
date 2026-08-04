---
name: assetslab
description: >-
  AssetsLab — Godot 像素角色动画工作流。骨架优先行走流水线 + 参数化动作引擎
  (motion pose library) + 工作流引擎 (CLI/Web 双通道 AI·人工调度) + 蒙皮/制品导出。
  纯 Python (Pillow) 工具链。给 AI 代理的调用手册：工作流调度、动作参数调优、
  风格模板、骨骼比例、Web/API、制品与 Godot demo。
---

# AssetsLab — AI 调用手册 (SKILL)

## 项目简介

Godot 4.7 像素风角色动画实验项目。核心是**骨架优先行走流水线** + **参数化动作引擎** + **工作流引擎**（AI/人工双通道调度）。工具链为纯 Python（Pillow），Godot 仅用于冒烟测试与最小可玩 demo。

## 环境

```bash
# 虚拟环境（依赖锁定在 requirements.txt: Pillow==12.3.0）
.venv/bin/python ...            # Linux/macOS
.venv\\Scripts\\python.exe ...   # Windows

# 启动预览服务器（含 REST API 与 Web 控制台）
.venv/bin/python workflow/tools/lan_preview_server.py --port 8765 --directory prototype/preview
# 或: .venv/bin/python workflow/tools/assetslab.py preview --port 8765
```

## 工作流引擎（AI 调度主入口）— `python -m workflow`

状态按实例持久化 `run/workflows/<workflow_id>/state.json`（git 忽略）。

```bash
python -m workflow list                                            # 列出实例（进度）
python -m workflow new --definition default --id hero --template cartoon --body-template chibi  # 新建（风格模板 + 体型模板）
python -m workflow status --workflow hero --json                   # 状态 + template + body + 各动作 params
python -m workflow next --workflow hero                            # 推荐下一步
python -m workflow run --workflow hero --action skeleton.front --json             # 用模板/默认参数运行
python -m workflow run --workflow hero --action skeleton.front --param stride=1.2 --param pelvis_bob=1.5   # 动作参数
python -m workflow run --workflow hero --action skeleton.front --body head_scale=1.4 --body height=1.1    # 本次体型覆盖
python -m workflow set-body --workflow hero --body head_scale=1.4  # 固化角色体型（实例级，三视图共享）
python -m workflow approve --workflow hero --action skeleton.front --by ai --note "ok"
python -m workflow reject --workflow hero --action skeleton.front --by ai --note "改大步幅"
python -m workflow history --workflow hero --json
```

**动作 id（7 步精简版）**：`skeleton.front` → `skeleton.side` → `skeleton.back` → `test.smoke` → `capture.walk` → `preview.publish` → `export.artifacts`。定义在 `workflow/definitions/default.json`。

**动作/体型分离**：动作参数（stride/bob/arm_swing）=「怎么动」，每动作可调；体型比例（arm_length…height）=「长什么样」，属于角色（实例级 `state.body`），三视图共享。两者正交。

**参数优先级**（动作参数）：运行时 `--param` > 实例模板 `template_params` > 定义默认值。
**体型优先级**（角色比例）：运行时 `--body` > 实例 `body`（`new --body-template`/`--body` 设定，`set-body` 修改）> 默认 1.0。

**风格参数模板**（`workflow/templates/*.json`）：`realistic`(写实 1.0/0.7/0.8)、`cartoon`(卡通 1.7/1.6/1.5)、`bouncy`(弹跳 1.3/2.0/1.2)、`heavy`(沉稳 1.6/1.8/0.9)、`light`(轻快 0.8/1.1/1.3) —— 顺序对应 stride/pelvis_bob/arm_swing。

**体型模板**（`workflow/body/*.json`）：`standard`(标准成人)、`chibi`(大头Q版)、`tall`(高挑模特)、`stocky`(矮壮力量型)。体型=角色属性，实例级共享。

## 动作引擎 — `workflow/tools/assetslab.py`

```bash
python workflow/tools/assetslab.py motion list|info <id>|render|check
python workflow/tools/assetslab.py motion render run --view front --stage arms --ik --proportion-head-scale 1.4
python workflow/tools/assetslab.py stage front arms --renderer python --motion walk --stride 1.2
python workflow/tools/assetslab.py stage front arms --renderer godot            # 一致性验证
```

- **动作预设**（pose library）：`workflow/motions/{walk,run,idle,jump}.json`，声明式（波形信号 + 相对 `base.json` 的关节偏移 + root + ik）。**新动作 = 新 JSON，无需改渲染器**。
- **一致性**：`motion check` 验证数据驱动 walk 与内置姿态逐像素一致（默认参数/比例下）。
- **渲染器**：`--renderer python`（默认，Pillow）vs `--renderer godot`（无头捕获，仅一致性/特殊候选）。

## 骨骼能力（参数化）

**运动参数**（每动作，怎么动）：`stride` 步幅、`pelvis_bob` 骨盆起伏、`arm_swing` 摆臂。
**体型比例**（角色属性，长什么样，实例级 `state.body` 三视图共享）：`arm_length`/`leg_length`/`torso_length`/`shoulder_width`/`head_scale`/`height`（1.0=基准）。与动作参数正交：同一动作可驱动任意体型，同一体型可配任意动作。工作流里用 `--body`/`set-body` 调；底层渲染器仍支持 `--proportion-*`。
**根驱动（root-driven）**：骨盆运动（bob/跳跃升降/前倾）通过 `base.json` 的 `torso` 继承系数传导到肩/臂/头——跳跃时肩/臂随骨盆整体升降（不再逐关节补丁）。
**双骨骼 IK**：`--ik`（run/jump 预设声明 `ik` 组），腿长恒定 + 脚落地锁定。

## Web 与 API

前端是 **Vue 3 + Element Plus + Tailwind CSS + Vite（pnpm）** 工程化 SPA，位于 `workflow/web/`；`pnpm build` 产出 `workflow/web/dist`，由 Python 服务端静态 serve（`lan_preview_server.py` 优先 serve dist，回退旧 `prototype/preview` 页面）。开发：`cd workflow/web && pnpm dev`（/api 代理到 :8765）。

- **`#/console`**：控制台（新建实例=定义+参数模板+体型模板、实例管理、动作预览台）
- **`#/wizard?id=<workflow_id>`**：分步流程向导（上一步/下一步，每步调动作参数→运行→评审；「角色体型」折叠面板改角色三视图）
- **API**（前缀 `http://127.0.0.1:8765`）：
  - `GET /api/workflow/list|templates|body-templates|definitions`
  - `GET /api/workflow/instances/<id>` / `.../next`
  - `POST /api/workflow/instances` （body: definition/id/template/body_template/body）
  - `POST /api/workflow/instances/<id>/body`（body: {body:{head_scale:1.4,…}}，固化角色体型）
  - `POST /api/workflow/instances/<id>/actions/<action_id>/{run|approve|reject}`（run 可带 `params` 动作参数 + `body` 体型覆盖）
  - `GET /api/motions`、`POST /api/motions/<id>/render`（body: view/stage/stride/pelvis_bob/arm_swing/ik/blend/blend_t/比例参数）
- 图片产物经 `http://127.0.0.1:8765/run/...` 提供（带 `?t=` 缓存失效）。

## 制品与 Godot demo

- 最后动作 `export.artifacts` 打包 `dist/<workflow_id>/`：`atlas/`（7 层 4 方向×8 帧）+ `runtime_manifest.json`（方向/层序/head_anchor_offsets/runtime_params）+ `character_walk_4way.gif`。
- 运行 demo：`godot --path prototype -- --artifacts dist/<workflow_id>`（WASD 移动 + 空格放炸弹）。
- 骨架/骨骼数据：`workflow/motions/base.json`（静态基座 + torso 层级）、`workflow/motions/*.json`（动作）。

## 给 AI 的推荐执行路径

1. `new --template <风格> --body-template <体型>` 建实例 → `status` 确认 template_params + body
2. `next` 取推荐动作 → `run`（`--param` 调动作、`--body` 调体型；也可先 `set-body` 固化角色）
3. `status --json` 看该动作 `outputs`（本地图片绝对路径）+ `params`（实际所用动作+体型）
4. 满意 `approve`（带 note）→ 不满意 `reject`（附调整建议）→ 重新 `run`
5. 走完 7 步 → `export.artifacts` → 制品供 Godot

## 约定与注意事项

- 渲染默认 `--renderer python`（Pillow）；`godot` 渲染器仅一致性验证（无头截图在本机不可用）。
- `run/`、`dist/`、`prototype/test_output/`、`.venv/` 均被 git 忽略。
- 新动作预设=新 JSON（`workflow/motions/`）；新风格模板=新 JSON（`workflow/templates/`）；新体型模板=新 JSON（`workflow/body/`）。
- 调整动作参数优先考虑风格模板；微调 `--param`；改角色体型用 `set-body`/`--body`（底层渲染器 `--proportion-*`）。动作参数与体型正交，勿混入动作定义。
- 修改骨架基座/动作后跑 `motion check` 确认与内置姿态一致。
- 预览服务器需用 `.venv` 解释器启动（依赖 Pillow）。
