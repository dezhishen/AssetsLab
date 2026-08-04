# AssetsLab（中文说明）

基于 **Godot 4.6.2** 的像素风角色动画实验项目。核心工作是：通过**「骨架验证先行、分层图集渲染、无头测试把关」**的流水线，自研 QQTang 风格（大头）角色**四方向 × 八帧**行走动画，并附带一个最小可玩原型作为运行时验证。

- 引擎：Godot 4.6.2（GL Compatibility 渲染，适合 2D 像素与跨平台/无头自动化）
- 方向：front / right / back / left 四方向，每方向 8 帧行走循环
- 运行时角色：7 层 `Sprite2D` 叠合（脚 / 下肢 / 手臂 / 躯干 / 耳朵 / 头 / 脸），头部与脸部外观由**确定性种子**选择
- 最小玩法：WASD/方向键移动，空格放置一枚短引信炸弹（爆炸会把玩家炸回出生点）

## 项目内容

| 模块 | 说明 |
|---|---|
| `prototype/` | Godot 4.6.2 工程：运行时脚本、分层资产、无头测试、浏览器预览页 |
| `tools/` | 工具链：资产构建 / 处理 / 校验（Python），无头测试与捕获（PowerShell） |
| `third_party/` | 开源参考素材（CC0 RGS 模块化角色、Female Adventurer 行走参考），仅作姿态时序参考，非最终美术风格 |
| `PROJECT.md` | 项目总纲：开发状态、路线图、评审原则（英文） |
| `references/` | 设计参考图：人体模型 sheet、正面角色锚点 |
| `prototype/assets/characters/walk_base/` | 权威 4 向行走基底源图 |
| `workflow/` | 工作流引擎 SDK：声明式定义 + CLI 调度 |
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
├── prototype/                 # Godot 4.6.2 工程
│   ├── project.godot
│   ├── main.tscn              # 主场景（角色 + 竞技场 + 墙体）
│   ├── scripts/               # 运行时 + 骨架流水线各阶段脚本
│   ├── assets/characters/     # 分层资产（chibi、faces、generated 候选等）
│   ├── tests/                 # 无头验证测试（smoke_test 等）
│   ├── preview/               # 浏览器预览页 + 交互校准页
│   └── README.md              # 原型的详细运行说明
├── tools/                     # 构建 / 校验 / 捕获 / 预览脚本
├── workflow/                  # 工作流引擎 SDK + 声明式定义
├── run/                       # 工作流实例状态（git 忽略，生成物）
└── third_party/               # 开源参考素材
```

## 快速开始

### 环境要求

- **Godot 4.6.2**：自动化脚本要求 `_console.exe` 无头构建（`--headless`）。解析顺序：`-GodotPath` → `GODOT_BIN`/`GODOT_PATH` → `PATH` 上的 `godot`/`godot4` → 相邻 `Godot-4.6.2` 目录。
- **Python 3 + Pillow**：资产处理与 GIF 合成需要。解析顺序：`-PythonPath` → `PYTHON_BIN` → `PATH` → 本地 `.venv`/相邻目录。
- PowerShell 脚本面向 Windows；跨平台 Python 工具在 Linux/macOS 上可直接运行。

所有命令默认在**仓库根目录**执行。

> **跨平台 CLI（推荐）：** `tools/assetslab.py` 是上述全部 PowerShell 脚本的跨平台镜像，
> 可在 Windows / Linux / macOS 上运行：`doctor`、`test`、`capture-walk`、
> `stage <视图> <阶段>`、`preview`、`publish`、`run-script`。参数与 .ps1 一致
> （`--female`、`--compact`、`--rebuild-head`、`--appearance-seed` 等），
> Godot 解析顺序为 `--godot` → `GODOT_BIN`/`GODOT_PATH` → `PATH` → 相邻 `Godot-4.6.2` 安装。
> 下方 PowerShell 脚本仍作为 Windows 的标准入口保留。

### 1. 运行无头冒烟测试

```powershell
# 生成随机外观包 -> 校验资产 -> 启动 Godot 冒烟测试
.\tools\run_headless_tests.ps1

# 常见参数
.\tools\run_headless_tests.ps1 -Female                                  # 女性基底
.\tools\run_headless_tests.ps1 -RebuildHead -VerticalCandidate          # 校准头 + 纵向候选
.\tools\run_headless_tests.ps1 -AppearanceSeed 20260730                 # 固定种子
.\tools\run_headless_tests.ps1 -GodotPath 'E:\Path\To\godot_console.exe' # 指定 Godot
```

**跨平台等价命令：**

```bash
python3 tools/assetslab.py test
python3 tools/assetslab.py test --female --rebuild-head --vertical-candidate
python3 tools/assetslab.py test --appearance-seed 20260730
python3 tools/assetslab.py test --godot /path/to/godot
```

### 2. 捕获行走动画 GIF

```powershell
.\tools\capture_walk_gif.ps1                       # 四方向行走 GIF -> prototype/test_output/
.\tools\capture_walk_gif.ps1 -RebuildHead -VerticalCandidate -VerticalOnly  # 仅纵向候选
.\tools\capture_walk_gif.ps1 -MilestoneBodyRight -RightOnly                 # 仅右向里程碑
```

**跨平台等价命令：**

```bash
python3 tools/assetslab.py capture-walk
python3 tools/assetslab.py capture-walk --rebuild-head --vertical-candidate --vertical-only
python3 tools/assetslab.py capture-walk --milestone-body-right --right-only
```

### 3. 骨架流水线（阶段推进）

```powershell
.\tools\capture_front_skeleton_stage.ps1    # front 静态骨架
.\tools\capture_front_leg_cycle_stage.ps1   # front 双腿循环
.\tools\capture_front_pelvis_bob_stage.ps1  # front 骨盆浮动
.\tools\capture_front_arm_swing_stage.ps1   # front 摆臂
# side / back 对应脚本同理
```

**跨平台等价命令：**

```bash
python3 tools/assetslab.py stage front skeleton
python3 tools/assetslab.py stage front legs
python3 tools/assetslab.py stage front pelvis
python3 tools/assetslab.py stage front arms
python3 tools/assetslab.py stage back legs
```

每阶段输出到 `prototype/test_output/skeleton_pipeline/`（PNG + GIF），必须在可视化验收通过后才进入下一阶段。

### 4. 本地预览

**Windows（一键发布 + 启动）：**

```powershell
.\tools\serve_preview.ps1 -SnapshotName my_review   # 发布快照并启动局域网服务器
.\tools\stop_preview.ps1                             # 停止服务器
```

**Linux / 跨平台（直接启动静态服务器）：**

```bash
python3 tools/lan_preview_server.py --port 8765 --directory prototype/preview
# 或等价：
python3 tools/assetslab.py preview --port 8765
# 打开 http://127.0.0.1:8765/  （服务器绑定 0.0.0.0，局域网设备可用 http://<本机IP>:8765/）
```

预览页汇总展示骨架流水线各阶段、当前基底、候选版本与 GIF；另有交互校准页 `/calibrate.html`、`/limb_calibrate.html`、`/body_calibrate.html`（校准数据经 API 保存到 `prototype/preview/calibration/`）。

### 5. 资产构建与处理

```bash
python tools/build_body_vertical_update.py   # 重建前/后纵向行走候选帧
# 或：python3 tools/assetslab.py run-script build_body_vertical_update.py
python tools/recolor_body_palettes.py        # 生成 light/warm/deep 肤色变体（保持尺寸与 alpha 不变）
python tools/build_preview_assets.py         # 重建预览资产集
python tools/publish_preview.py --name tag   # 发布时间戳快照到 preview/snapshots/
```

### 6. 工作流引擎（AI / 人工调度）

`tools/workflow.py` 以**步进式**驱动流水线，状态按实例持久化到 `run/workflows/<workflow_id>/`：

```bash
python tools/workflow.py list                                            # 列出实例
python tools/workflow.py new --definition default --id review-a          # 新建实例
python tools/workflow.py status --workflow review-a --json               # 查看状态
python tools/workflow.py next --workflow review-a                        # 推荐下一步
python tools/workflow.py run --workflow review-a --action skeleton.front.legs --json
python tools/workflow.py approve --workflow review-a --action skeleton.front.legs --by ai --note "ok"
python tools/workflow.py reject --workflow review-a --action skeleton.front.legs --by human --note "redraw"
```

- **CLI** 是面向 AI 的调度通道：`--json` 输出机器可读，`outputs` 返回本地图片**绝对路径**。
- **Web** 是面向人工的完整通道：`http://<host>:8765/workflow.html`；图片经 `http://<host>:8765/run/workflows/<id>/steps/<action_id>/` 预览。
- `workflow_id` / `action_id` 贯穿 CLI、Web、持久化三层；多实例可**并行**，各自分文件存储。

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
