# AssetsLab（中文说明）

基于 **Godot 4.7** 的像素风角色动画实验项目。核心工作是：通过**「骨架验证先行、分层图集渲染、无头测试把关」**的流水线，自研 QQTang 风格（大头）角色**四方向 × 八帧**行走动画，并附带一个最小可玩原型作为运行时验证。

- 引擎：Godot 4.7（GL Compatibility 渲染，适合 2D 像素与跨平台/无头自动化）
- 方向：front / right / back / left 四方向，每方向 8 帧行走循环
- 运行时角色：7 层 `Sprite2D` 叠合（脚 / 下肢 / 手臂 / 躯干 / 耳朵 / 头 / 脸），头部与脸部外观由**确定性种子**选择
- 最小玩法：WASD/方向键移动，空格放置一枚短引信炸弹（爆炸会把玩家炸回出生点）

## 项目内容

| 模块 | 说明 |
|---|---|
| `prototype/` | Godot 4.7 工程：运行时脚本、分层资产、无头测试、浏览器预览页 |
| `third_party/` | 开源参考素材（CC0 RGS 模块化角色、Female Adventurer 行走参考），仅作姿态时序参考，非最终美术风格 |
| `PROJECT.md` | 项目总纲：开发状态、路线图、评审原则（英文） |
| `references/` | 设计参考图：人体模型 sheet、正面角色锚点 |
| `prototype/assets/characters/walk_base/` | 权威 4 向行走基底源图 |
| `workflow/` | 工作流引擎：SDK + 工具（assetslab、构建、校验）+ 定义 |
| `run/` | 工作流实例状态（git 忽略）：state.json + 步骤图片产物 |

### 核心方法论：骨架优先行走流水线

先用 Godot `_draw()` **程序化绘制的骨架**验证姿态时序与层次规则，验证通过后才据此重绘像素资产。每个方向按阶段递进，每阶段有独立脚本 + 无头捕获 + 内置断言：

1. **静态基准骨架**：对称性、共享脚基线
2. **八帧腿循环**：交替接触/迈步（F0/F4 为接触帧，前半循环左腿在前、后半右腿在前）
3. **骨盆垂直浮动**：仅 ≤6px 峰峰值起伏
4. **反向手臂摆动**：与对应腿反相，手不越中线

进度：**front 与 side 已通过全部 4 阶段，back 停留在八帧腿循环**。每阶段产物与门槛记录在 `prototype/assets/characters/generated/skeleton_walk_pipeline_v1/` 的 manifest JSON 中。

## 目录结构

```text
assets-lab/
├── PROJECT.md                 # 项目总纲（英文）
├── README.md                  # 英文版项目说明
├── README_ZH.md               # 中文版项目说明（本文件）
├── references/                # 设计参考图（人体模型 sheet、角色锚点）
├── prototype/                 # Godot 4.7 工程
│   ├── project.godot
│   ├── main.tscn              # 主场景（角色 + 竞技场 + 墙体）
│   ├── scripts/               # 运行时 + 骨架流水线各阶段脚本
│   ├── assets/characters/     # 分层资产（chibi、faces、generated 候选等）
│   ├── tests/                 # 无头验证测试（smoke_test 等）
│   ├── preview/               # 浏览器预览页 + 交互校准页
│   └── README.md              # 原型的详细运行说明
├── workflow/                  # 工作流引擎：SDK + 工具 + 定义
│   ├── tools/                 # 可执行脚本（assetslab、捕获、构建、校验）
│   └── definitions/           # 声明式工作流定义
├── run/                       # 工作流实例状态（git 忽略，生成物）
└── third_party/               # 开源参考素材
```

## 快速开始

### 环境要求

- **Godot 4.7**：自动化脚本要求 `_console.exe` 无头构建（`--headless`）。解析顺序：`--godot` → `GODOT_BIN`/`GODOT_PATH` → `PATH` 上的 `godot`/`godot4` → 相邻 `Godot-4.7` 目录。
- **Python 3 + Pillow**（通过虚拟环境）：资产处理与 GIF 合成需要。解析顺序：`--python` → `PYTHON_BIN` → 本地 `.venv` → `PATH`。
- 全部为**纯 Python 跨平台**方案，不依赖任何 PowerShell / shell 脚本。

### 虚拟环境（推荐）

所有 Python 工具运行在 `.venv/` 中，依赖相互隔离；解析器会自动优先使用它。

```bash
# 首次创建
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# 可选：激活后 `python` 指向 venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 推荐：直接用 venv 解释器（无需激活）
.venv/bin/python workflow/tools/assetslab.py doctor
.venv/bin/python -m workflow list
```

Windows 使用 `.venv\Scripts\python.exe`。`requirements.txt` 固定 Python 依赖（Pillow）。

所有命令默认在**仓库根目录**执行。

> **CLI（统一入口）：** `workflow/tools/assetslab.py` 可在 Windows / Linux / macOS
> 上运行：`doctor`、`test`、`capture-walk`、`stage <视图> <阶段>`、`preview`、
> `publish`、`run-script`。参数：`--female`、`--compact`、`--rebuild-head`、
> `--appearance-seed` 等；Godot 解析顺序为 `--godot` → `GODOT_BIN`/`GODOT_PATH` → `PATH` → 相邻 `Godot-4.7` 安装。

### 1. 运行无头冒烟测试

```bash
# 生成随机外观包 -> 校验资产 -> 启动 Godot 冒烟测试
python workflow/tools/assetslab.py test

# 常见参数
python workflow/tools/assetslab.py test --female                                  # 女性基底
python workflow/tools/assetslab.py test --rebuild-head --vertical-candidate          # 校准头 + 纵向候选
python workflow/tools/assetslab.py test --appearance-seed 20260730                 # 固定种子
python workflow/tools/assetslab.py test --godot 'E:\Path\To\godot_console.exe' # 指定 Godot
```

**跨平台等价命令：**

```bash
python3 workflow/tools/assetslab.py test
python3 workflow/tools/assetslab.py test --female --rebuild-head --vertical-candidate
python3 workflow/tools/assetslab.py test --appearance-seed 20260730
python3 workflow/tools/assetslab.py test --godot /path/to/godot
```

### 2. 捕获行走动画 GIF

```bash
python workflow/tools/assetslab.py capture-walk                       # 四方向行走 GIF -> prototype/test_output/
python workflow/tools/assetslab.py capture-walk --rebuild-head --vertical-candidate --vertical-only  # 仅纵向候选
python workflow/tools/assetslab.py capture-walk --milestone-body-right --right-only                 # 仅右向里程碑
```

**跨平台等价命令：**

```bash
python3 workflow/tools/assetslab.py capture-walk
python3 workflow/tools/assetslab.py capture-walk --rebuild-head --vertical-candidate --vertical-only
python3 workflow/tools/assetslab.py capture-walk --milestone-body-right --right-only
```

### 3. 骨架流水线（阶段推进）

```bash
python workflow/tools/assetslab.py stage front skeleton    # front 静态骨架
python workflow/tools/assetslab.py stage front legs   # front 双腿循环
python workflow/tools/assetslab.py stage front pelvis  # front 骨盆浮动
python workflow/tools/assetslab.py stage front arms   # front 摆臂
# side / back 对应脚本同理
```

**跨平台等价命令：**

```bash
python3 workflow/tools/assetslab.py stage front skeleton
python3 workflow/tools/assetslab.py stage front legs
python3 workflow/tools/assetslab.py stage front pelvis
python3 workflow/tools/assetslab.py stage front arms
python3 workflow/tools/assetslab.py stage back legs
```

每阶段输出到 `prototype/test_output/skeleton_pipeline/`（PNG + GIF），必须在可视化验收通过后才进入下一阶段。

### 4. 本地预览

**Windows（一键发布 + 启动）：**

```bash
python workflow/tools/lan_preview_server.py --port 8765 --directory prototype/preview --name my_review   # 发布快照并启动局域网服务器
# stop: kill the lan_preview_server process                             # 停止服务器
```

**Linux / 跨平台（直接启动静态服务器）：**

```bash
python3 workflow/tools/lan_preview_server.py --port 8765 --directory prototype/preview
# 或等价：
python3 workflow/tools/assetslab.py preview --port 8765
# 打开 http://127.0.0.1:8765/  （服务器绑定 0.0.0.0，局域网设备可用 http://<本机IP>:8765/）
```

预览页汇总展示骨架流水线各阶段、当前基底、候选版本与 GIF；另有交互校准页 `/calibrate.html`、`/limb_calibrate.html`、`/body_calibrate.html`（校准数据经 API 保存到 `prototype/preview/calibration/`）。

### 5. 资产构建与处理

```bash
python workflow/tools/build_body_vertical_update.py   # 重建前/后纵向行走候选帧
# 或：python3 workflow/tools/assetslab.py run-script build_body_vertical_update.py
python workflow/tools/recolor_body_palettes.py        # 生成 light/warm/deep 肤色变体（保持尺寸与 alpha 不变）
python workflow/tools/build_preview_assets.py         # 重建预览资产集
python workflow/tools/publish_preview.py --name tag   # 发布时间戳快照到 preview/snapshots/
```

### 6. 工作流引擎（AI / 人工调度）

`-m workflow` 以**步进式**驱动流水线，状态按实例持久化到 `run/workflows/<workflow_id>/`：

```bash
python -m workflow list                                            # 列出实例
python -m workflow new --definition default --id review-a          # 新建实例
python -m workflow status --workflow review-a --json               # 查看状态
python -m workflow next --workflow review-a                        # 推荐下一步
python -m workflow run --workflow review-a --action skeleton.front --json
python -m workflow approve --workflow review-a --action skeleton.front --by ai --note "ok"
python -m workflow reject --workflow review-a --action skeleton.front --by human --note "redraw"
```

**动作参数化** — 每个动作可在定义里声明可调旋钮（如 `stride` / `pelvis_bob` / `arm_swing`），运行时可覆盖任意参数，实际使用的参数会记录进该动作状态供评审：

```bash
python -m workflow run --workflow review-a --action skeleton.front --param stride=1.2 --param pelvis_bob=1.5 --json
```

**风格参数模板** — 不必从中性参数（stride=1.0）开始，创建实例时可直接选一套业内风格默认参数（`--template realistic|cartoon|bouncy|heavy|light`）。模板值成为该实例的默认旋钮（每次运行仍可用 `--param` 覆盖）；Web 控制台新建实例时提供同样的模板选择，并会用它预填向导的参数滑块。

```bash
python -m workflow new --definition default --id hero --template bouncy
python -m workflow run --workflow hero --action skeleton.front              # 用 bouncy 默认参数
python -m workflow run --workflow hero --action skeleton.front --param stride=1.5   # 覆盖单个旋钮
```

- **CLI** 是面向 AI 的调度通道：`--json` 输出机器可读，`outputs` 返回本地图片**绝对路径**。
- **Web** 是面向人工的完整通道：`http://<host>:8765/workflow.html`；图片经 `http://<host>:8765/run/workflows/<id>/steps/<action_id>/` 预览。带可调参数的动作在运行前会弹出**参数调优窗**（拖动 stride/pelvis-bob/arm-swing 再运行），人真正参与调姿态，而不只是点「通过」。
- **分步流程向导**：`http://<host>:8765/flow.html?id=<workflow_id>` 一次只渲染一个步骤（步进器 + 上一步/下一步，类似安装向导）。每步展示参数、输出与评审按钮；`workflow.html` 中点击实例即进入向导。首次打开优先定位「已通过但未审核」的步骤（先补审核），否则定位推荐的下一步。
- `workflow_id` / `action_id` 贯穿 CLI、Web、持久化三层；多实例可**并行**，各自分文件存储。

## 预览渲染（纯 Python）

骨架流水线预览改用 Pillow 渲染（`workflow/tools/render_skeleton_preview.py`），无需 Godot。姿态参数化，AI 可直接调优：

```bash
python workflow/tools/assetslab.py stage front legs --renderer python --stride 1.2 --pelvis-bob 1.0 --arm-swing 1.1
python workflow/tools/render_skeleton_preview.py --view side --stage arms --arm-swing 1.5
```

- `--stride` 步幅 · `--pelvis-bob` 骨盆浮动 · `--arm-swing` 摆臂幅度。
- 工作流的骨架动作已默认 `--renderer python`；Godot 无头捕获仍以 `--renderer godot` 保留用于一致性验证。

### 数据驱动动作预设（姿态库）

不再把姿态写成散落的函数，而是把动画循环做成**声明式 JSON 预设**，放在 `workflow/motions/`（`walk`、`run`、`idle`、`jump`）。每个预设描述「波形信号 + 相对静态基座的关节偏移」，由引擎（`workflow/tools/motion.py`）采样成帧。**新增一个动作 = 新增一个 JSON 文件，无需改渲染器**。

```bash
python workflow/tools/assetslab.py motion list                          # 列出预设
python workflow/tools/assetslab.py motion info run                      # 查看参数与 IK 组
python workflow/tools/assetslab.py motion render run --view front --stage legs --ik
python workflow/tools/assetslab.py motion check                         # walk == 内置姿态
python workflow/tools/assetslab.py stage side arms --renderer python --motion run --ik
```

- `walk` 为参照预设：`motion check` 与像素级对比证明它与 Godot 一致的旧内置姿态**逐像素完全相同**（全部视图/阶段）。
- **头部运动**：`head`/`neck` 以骨盆起伏的一半幅度跟随浮动，侧视图还有前后摆动——经典的「反向补偿」动画，头不再锁死（walk/run 上下浮动、idle 呼吸点头、jump 随身体升降）。
- **骨骼层级（根驱动）**：关节构成刚性躯干链（pelvis → neck/head + shoulders/arms）。每个动作声明 `root`（骨盆平移：bob / 跳跃升降 / 前倾），躯干上的每个关节按各自系数继承它（`base.json` 的 `torso`）：肩/臂 1.0（刚性）、膝 0.5（衰减）、头 0.5（视线稳定）。跳跃时肩/臂随骨盆整体升降，无需逐关节补丁。
- **双骨骼 IK**（`--ik`；预设内声明 `ik` 组）在大步幅下保持腿长恒定，并做「落地锁定」——脚目标超出可达半径时锁定回可达边界，用于 `run` / `jump`。
- **跨动作混合**：`--blend run --blend-t 0.5` 对关节做插值，实现 walk↔run 参数化过渡。
- **Web**：工作流控制台 `/workflow.html` 新增 **动作预览台（Motion Studio）**——选动作/视角/阶段、拖动 stride/pelvis-bob/arm-swing 滑块、勾选 IK、跨动作混合，浏览器内通过 `POST /api/motions/<id>/render` 实时渲染循环。

## 制品与 Godot demo

工作流的最后一个动作 `export.artifacts` 会用纯 Python（无需 Godot）在 `dist/<workflow_id>/` 下打包一份**Godot 可直接使用**的制品：

```text
dist/<workflow_id>/
├── atlas/                      # 分层 4×8 帧（feet/lower_body/arms/torso/head_base/ear/face）
├── runtime_manifest.json       # 方向、层序、head_anchor_offsets
├── character_walk_4way.gif     # Pillow 合成预览
└── README.md
```

用最小可运行 demo（保留交互玩法）加载制品：

```bash
godot --path prototype -- --artifacts dist/<workflow_id>
```

demo 保留 WASD/方向键移动与空格放炸弹的交互验证。

## 输出位置与说明

| 产物 | 路径 | Git |
|---|---|---|
| 测试 / 捕获输出 | `prototype/test_output/` | 忽略 |
| 随机外观包 | `prototype/test_output/random_appearance/` | 忽略 |
| 预览快照 | `prototype/preview/snapshots/` | 忽略 |
| 运行时分层资产 | `prototype/assets/characters/chibi/` | 跟踪 |
| 生成候选 / 骨架流水线 | `prototype/assets/characters/generated/` | 跟踪 |

## 当前状态与路线图

- **已完成**：front / side 骨架完整循环（骨架→腿→骨盆→摆臂）；back 八帧腿循环；校准头部运行时；确定性种子外观。
- **进行中**：back 骨盆/摆臂 → 验证左镜像 → 四方向锚点审查 → 身体块与头部附着校准。
- **待办**：男/女变体、模块化随机脸/发/服装层、垂直行走候选并入运行时、斜向方向（推迟至四方向契约稳定）。
- **已归档**：被否决的 AI 身体/头部实验、Skeleton2D 实验等保留在 `history0731` 分支供审计，不在主线路资产集中。

## 相关文档

- [`README.md`](README.md) — 英文版项目说明
- [`PROJECT.md`](PROJECT.md) — 项目总纲：开发状态、候选评审与资源清理（英文）
- [`prototype/README.md`](prototype/README.md) — 原型的详细技术说明与全部命令
- [`prototype/preview/README.md`](prototype/preview/README.md) — 预览页的构建与发布说明
