# 蒙皮流程（Skinning Pipeline）—— 皮肤 = 部件 + 骨骼

> 分支：`feat/skinning` ｜ 状态：**已实现（程序化人体模特皮肤 + 烘焙成 demo 制品）**

## 一、定位

把**程序化皮肤**「蒙」到**数据驱动骨架**上，实现程序化蒙皮动画：

- **皮肤（skin）**：独立皮肤包 `skins/<id>/`，含部件图（head/neck/肢体段…）+ 绑点定义（锚点=部件图中心=关节）
- **骨骼（base.json + motions/*.json）**：关节坐标采样 + 体型比例 + IK
- **蒙皮** = `skin_frame` 逐帧按骨架关节实时合成部件（平移 + `rotate_child` 旋转），肢体段从关节沿骨骼方向旋转，rest 天然贴合
- **成品**：`export_skin_demo.py` 把蒙皮**烘焙**成预烘焙分层帧制品（`dist/<name>/`），供 Godot demo 直接运行

> 与早期方案的差异：不再用「atlas 静态分层部件」做蒙皮素材，而是**程序化几何部件**（人体模特/种族角色），`coordinates="skeleton"` 下锚点=图中心=关节，天然贴合；蒙皮结果通过烘焙环节进入制品管线。

## 二、皮肤包结构（skins/<id>/）

```
skins/<id>/
├── skin.json            # 定义：layout=pack, coordinates=skeleton, body(固化体型), layers, bindings
├── 000_head_front.png   # 部件图：<3位序号>_<层名>_<视图>.png（13 层 × 3 视图 front/side/back）
├── 001_neck_front.png
├── 100_upper_arm_left_front.png
├── …                     # 其余 10 层
└── preview/             # 渲染出的动画（GIF + PNG 帧序列）
```

- **序号按身体区域分段（3 位）**：`000`头颈 / `100`左臂 / `200`右臂 / `300`躯干 / `400`左腿 / `500`右腿 / `600`脚（每区预留 100 槽，便于扩展）。
- **coordinates="skeleton"**：锚点 = 部件图中心（精确=关节）；肢体段从锚点沿 +x 水平延伸，按骨骼段方向旋转（`rotate_child`），rest 天然贴合。
- **bindings**：每层声明 `joint` + 可选 `rotate_child`，如 `upper_arm_left → {joint: shoulder_left, rotate_child: left_elbow}`。
- **body**：固化生成时的体型（8 项段参数），烘焙/渲染免再传参。

## 三、皮肤生成（build_mannequin_skin.py）

人体模特皮肤可按**体型实例化 + 配色**：

```bash
python workflow/tools/build_mannequin_skin.py \
    --body head_scale=1.15 --body neck_length=0.9 --body torso_length=1.15 \
    --body shoulder_width=1.4 --body upper_arm_length=1.2 --body forearm_length=1.2 \
    --body thigh_length=1.1 --body shin_length=1.1 \
    --palette orc --out orc
```

- `--body NAME=VALUE`：8 项段参数（可重复）；体型会写进 `skin.json`（`body` 字段）
- `--palette`：配色表 `default` / `orc`(绿) / `human`(蓝) / `undead`(暗灰) / `dwarf`(棕)（`PALETTES` 常量）
- `--out <name>`：皮肤包名，生成 `skins/<out>/`

## 四、体型参数（8 项段参数，无整体身高）

`head_scale` / `neck_length` / `torso_length` / `shoulder_width` / `upper_arm_length` / `forearm_length` / `thigh_length` / `shin_length`（各 1.0=基准）。

按**骨骼段独立缩放**（每段绕锚点），没有整体 `height`——避免整体缩放带来的连锁比例错误（如脖子过长/头身失衡）。头随 `head_scale` 缩放。

## 五、蒙皮引擎（workflow/tools/skin.py）

- `skin_frame(motion, view, stage, index, params, proportions, skin, atlas_dir, layout, only_layers=None)`：逐帧合成；`only_layers` 支持分层渲染（烘焙用）。
- `rotate_to_joint`：肢体段绕锚点（图中心）旋转到「关节→子关节」方向，`PIL rotate(-deg)`。
- **side 视图深度排序**（`_side_layer_order`）：后侧肢体（`_right`→rear）最底 → 躯干 → 脖子 → 前侧肢体（`_left`→front）→ 头最顶，避免后腿/后臂穿透躯干导致闪烁。
- **VIEW_JOINT 视图映射**：side 下 `left_`→`front_`、`right_`→`rear_`（前/后肢分开，不再重叠成一条）；back 手臂用 `rear_` 侧、腿用 `left_/right_` 直接键。
- **命令**：`list` / `anchors` / `render` / `verify`。注意 **`verify` 的第一个位置参数是 atlas（非 skin）**——正确用法 `skin.py verify --skin <id>`。
- CLI 入口：`assetslab.py skin list|anchors|render|verify --skin <id>`（`--skin` 已支持 `skins/` 皮肤包）。

## 六、烘焙成制品（workflow/tools/export_skin_demo.py）

皮肤是程序化几何，Godot demo（`player.gd`）消费**预烘焙分层帧**。烘焙 = 把皮肤逐帧渲染成 demo 的 7 层帧 + manifest：

```bash
python workflow/tools/export_skin_demo.py --skin orc [--out orc]   # → dist/orc/
```

- **层映射**（皮肤 13 层 → demo 7 层）：`feet`→foot_*、`lower_body`→thigh/shin_*、`arms`→upper_arm/forearm_*、`torso`→{torso,neck}、`head_base`→head、`ear`/`face`→空层。
- **方向**：`front`→front、`right`→side、`back`→back、`left`→side 镜像。
- 每方向整帧 bbox 统一变换（裁剪+缩放+底部对齐），层叠加=完整角色。
- **`layer_y=-26.0`**（匹配 `main.tscn` 里 body 层 sprite 位置 `(0,-26)`，否则 head sprite 被放到 `(0,layer_y)` 脱离躯干）。
- 输出 `dist/<name>/`：`atlas/`(4×8) + `runtime_manifest.json` + `character_walk_4way.gif` + `README.md`。`dist/` 被 gitignore，可从皮肤随时重烘焙。

## 七、Godot demo（prototype/）

```bash
godot --path prototype -- --artifacts dist/orc        # 空格 / 等号两种写法均可
godot --path prototype -- --artifacts=dist/orc
```

- `player.gd` 已修复 `--artifacts` 解析：支持 `--artifacts dist/x` 与 `--artifacts=dist/x`；加载完成打印 `ARTIFACTS_LOADED dir=… layers=7 frames=224` 便于确认。
- **皮肤模式**（预览皮肤动画，可选）：`--skin-mode --skin-pack=<name> --skin-view=front`。
- `scripts/build_demo.sh` / `.bat`：制品驱动，扫描 `dist/` 列出制品供选择运行。

## 八、现有皮肤

| 皮肤 | 体型/配色 | 说明 |
|---|---|---|
| `mannequin` | 标准 1.0 / default | 基础人体模特 |
| `mannequin_swordswoman` | 高挑(头 0.95/腿 1.3) / default | 剑士体型 |
| `orc` | 宽肩强壮(肩 1.4/头 1.15) / orc 绿 | 兽人战士 |
| `human_warrior` | 标准壮(肩 1.2) / human 蓝 | 人类战士 |
| `undead` | 瘦长(颈 1.3/肩 0.75) / undead 暗灰 | 亡灵 |
| `dwarf` | 矮壮(头 1.25/腿 0.7) / dwarf 棕 | 矮人 |
| `skeleton` | legacy 预烘焙 | 旧格式 `workflow/skins/skeleton.json` |

## 九、修复记录 / 经验

- **顺拐**根因 = 手臂 **y 方向相位**（front/back 视图摆臂视觉主信号是手的上下；只看 x 会漏判）。修 `walk.json` front/back 手臂 y 用对侧信号。
- **side 只有一只手一只脚** = `VIEW_JOINT` side 把左右都映射到 `front_`（重叠成一条）；改 left→front_、right→rear_。
- **side 闪烁** = 后腿/后臂画在躯干前（合成顺序）；加 side 深度排序。
- **demo 脑袋错位** = 制品 `layer_y` 不匹配 `main.tscn` body sprite 位置（应为 -26）。
- **demo 未用注入制品** = `--artifacts` 只认等号、空格被忽略；改同时支持两种。

## 十、工作流补充

`workflow/definitions/default.json` 在 `export.artifacts` 之后追加 `skin.verify` + `skin.render`：

```
… → export.artifacts → skin.verify → skin.render
```

- `skin.verify`：校验 bindings 关节存在 + rest 合成帧
- `skin.render`：程序化蒙皮合成（`--param skin/motion/view`），输出皮肤包 `preview/`
