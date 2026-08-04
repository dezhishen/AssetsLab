# 蒙皮流程方案（Skinning Pipeline）

> 分支：`feat/skinning` ｜ 状态：**已实现（M1-M6）**

## 一、定位与目标

把项目已有的两套系统打通，实现**程序化蒙皮动画**：

- **骨架系统（成熟）**：`workflow/motions/base.json`（关节 rest pose + `torso` 传导）+ `workflow/motions/*.json`（波形/偏移/root/IK）+ `workflow/tools/motion.py`（关节坐标采样）
- **成品分层（atlas）**：`dist/<id>/atlas/{feet,lower_body,arms,torso,head_base,ear,face}`（4×8 预烘焙帧）+ 运行时平铺叠放（`player.gd` 7 个 Sprite2D）

当前两者**脱节**：骨架只渲染线条预览（`render_skeleton_preview.py` 画 bone/joint），成品是预烘焙帧、不随关节运动。

**蒙皮 = 把 atlas 部件「蒙」到骨骼关节上**：
- 部件（torso/lower_body/arms/feet/head/ear/face）绑定到关节
- 动作驱动关节 → 部件跟随（平移 + 可选旋转）
- 取代/补充「预烘焙帧平铺」，实现数据驱动的程序化动画

## 二、素材来源

**结论：蒙皮素材大部分是现有资产复用，只有「部件锚点 + 绑定定义」需要新增，且锚点可从现有体系继承 + 自动提取。**

| 素材 | 来源 | 状态 |
|---|---|---|
| 部件图像（atlas 分层） | `dist/<id>/atlas/{feet,lower_body,arms,torso,head_base,ear,face}`（更上游 `prototype/assets/characters/`：chibi 运行时 / rebuild_atlas_v1_runtime） | ✅ 现有，直接复用 |
| 骨骼 / 关节 | `workflow/motions/base.json`（front/side/back 关节 + torso 传导） | ✅ 现有，直接复用 |
| 部件锚点 | ① **已有**：`head_anchor_offsets`（head/ear/face，每方向）已在 runtime_manifest；`body_anchor_offsets`（body 相对头）player.gd 已支持<br>② **新增**：arms/torso/lower_body/feet 锚点 → `extract_skin_anchors.py` 从 atlas 部件自动提取（包围盒/端点/重心），人工校准兜底 | 🔶 部分现有 + 新增提取 |
| 绑定关系（部件→关节） | 基于骨架层次 + 部件对齐，`skins/<name>.json` 声明；半自动生成 + 人工确认 | 🆕 需定义 |

> 关键：head/ear/face 锚点**已有现成数据**（head_anchor_offsets），蒙皮 M1 可先打通头部，再补身体部件锚点。

## 三、分层架构

```
蒙皮 = 骨骼（已有） × 绑定定义（新） × 部件锚点（新）
```

> **关键实现发现**：atlas 各层帧是「静态部件」而非动画帧（同一层 frame0~frame7 的 alpha bbox 基本不变，±1px）。因此蒙皮 = 把静态部件**程序化贴到骨架关节**，骨架坐标缩放（scale）适配部件尺寸，offset 校准 rest 对齐。

### 1. 骨骼层次（复用，不新增）
- `base.json` 关节：head/neck/shoulder/elbow/hand/pelvis/hip/knee/foot（front/side/back 三视图）
- `torso` 传导表：各关节继承骨盆运动的权重（1.0 刚性 / 0.5 阻尼）——已实现「根驱动」

### 2. 蒙皮绑定定义（新增 `workflow/skins/<name>.json`）
```json
{
  "schema": "assetslab_skin_v1",
  "views": ["front", "side", "back"],
  "bindings": {
    "torso":      { "joint": "pelvis",            "anchor": [0, 0], "rotate": false },
    "lower_body": { "joint": "pelvis",            "anchor": [0, 0], "rotate": false },
    "arms":       { "joint": "shoulder_%s",       "anchor": [0, 0], "rotate": true },
    "feet":       { "joint": "foot_%s",           "anchor": [0, 0], "rotate": false },
    "head_base":  { "joint": "head",              "anchor": [0, 0], "rotate": false },
    "ear":        { "joint": "head",              "anchor": [0, 0], "rotate": false },
    "face":       { "joint": "head",              "anchor": [0, 0], "rotate": false }
  },
  "limbs": { "arms": "left/right", "feet": "left/right" }
}
```
- 每层：主关节、锚点（部件在层内参考点）、是否随关节旋转、支链（`%s` = left/right）

### 3. 部件锚点提取（新增 `workflow/tools/extract_skin_anchors.py`）
- 分析 atlas 分层 PNG，提取每层几何特征（包围盒、端点、重心）
- 半自动标注锚点：手臂根部（shoulder 端）、头颈连接、脚底基线等
- 输出锚点 JSON，与绑定定义交叉校验

### 4. 蒙皮引擎（`workflow/tools/skin.py`，已实现）
- 输入：`base.json` + motion 预设 + atlas 分层 + `skins/*.json`
- 流程：
  1. 复用 `motion.pose()` 采样关节坐标（含比例缩放 / root 传导 / IK）
  2. `skin_layout()` 计算骨架->部件画布的 scale（部件高/骨架高）+ offset（rest 校准）
  3. 单侧层：部件锚点对齐其关节；成对层（arms/feet 含左右）：整体贴到各支链关节中点
  4. Pillow 合成帧 → PNG 帧序列 + GIF
- 验证：`verify` 输出 rest 贴合 IoU（程序化蒙皮 vs frame 对齐参考），无需看图即可量化贴合度
- 锚点：启发式（center/top_center/bottom_center）为基线；`skin anchors` 提取后可手动校准进 `skin.anchors` 提升贴合

### 5. 皮肤可替换（已实现）
- 皮肤 = 独立**皮肤包** `skins/<name>/`（`skin.json` + 标准命名部件 `<NN>_<layer>_<view>.png`（数字序号前缀）+ `preview/` 预览动画），**不在制品里**
- 换皮肤 = 新建一个皮肤包目录；`--skin` 驱动，CLI / 工作流 / Godot 均支持
- 默认 `mannequin` 皮肤（人体模特）在 `skins/mannequin/`；预烘焙 `skeleton` 皮肤在 `workflow/skins/skeleton.json`（绑定实例 atlas）

## 三、工作流补充（default.json，已实现）

骨架阶段之后、捕获之前插入蒙皮阶段：

```
skeleton.front → skeleton.side → skeleton.back → test.smoke → capture.walk → export.artifacts → skin.verify → skin.render
```

- `skin.verify`：校验 `skins/*.json` 的 joint 存在于 base、锚点已提取、支链完整 + rest 贴合 IoU
- `skin.render`：程序化蒙皮合成（可 `--param skin/motion/view` 切换皮肤与视图），输出 `dist/<id>/skins/`（GIF + PNG 帧序列）

## 四、Godot 运行时

- `player.gd`：`--skin-mode`（可选）加载 `dist/<id>/skins/<skin>_<motion>_<view>/frameN.png` 序列，用 `--skin-view front|side|back` 选视图；蒙皮帧覆盖预烘焙 7 层显示
- 保留预烘焙帧平铺作为回退；蒙皮为「数据驱动 + 程序化」路径（运行时实时贴关节为未来扩展）

## 五、验证

- `skin.verify`：逐帧校验部件贴合关节、无穿帮、无异常拉伸
- 蒙皮 GIF 与预烘焙帧（`character_walk_4way.gif`）对比

## 六、里程碑（全部完成）

| 阶段 | 内容 | 产物 | 状态 |
|---|---|---|---|
| M1 | 蒙皮 schema + 锚点提取 | `workflow/skins/skeleton.json` + `skin anchors` | ✅ |
| M2 | 蒙皮引擎（缩放适配 + 成对层 + IoU 验证） | `workflow/tools/skin.py` | ✅ |
| M3 | skin 命令接入 | `assetslab skin list/anchors/render/verify` | ✅ |
| M4 | 工作流补充 | `default.json` 追加 `skin.verify`/`skin.render` | ✅ |
| M5 | 皮肤可替换 | 皮肤自包含 `atlas_dir` + `--skin`；换肤 = 新建定义 | ✅ |
| M6 | Godot 运行时蒙皮 | `player.gd --skin-mode` 播放蒙皮序列 | ✅ |
| M7 | 验证 + 文档 | 本文件 + SKILL.md + 制品 `dist/精灵女弓箭手/skins/` | ✅ |

**验证基线**（`assetslab skin verify --skin skeleton`，rest 贴合 IoU vs frame 对齐）：front=0.683 / side=0.557 / back=0.568。锚点手动校准可进一步提升。

## 七、风险与权衡

- **锚点质量**：部件锚点直接决定蒙皮贴合度 → 提取工具 + 人工标注兜底
- **性能**：程序化合成 vs 预烘焙帧 → 蒙皮用于预览/验证，成品仍可用预烘焙帧
- **兼容**：蒙皮是新路径，不影响现有 6 步工作流（追加阶段）
