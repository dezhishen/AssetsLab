# AssetsLab — 数据驱动角色素材管线
## 类型声明

`assetslab/models.py` — 完整 Python TypedDict 类型声明，面向人类和 AI 的可读文档。
定义了 Species → Preset → Motion 三层数据模型及所有 API 响应类型。

## 存储结构

```
assetslab/
  species/                    ← 物种（文件夹式，细颗粒度管理）
    human/                    ← 每个物种一个文件夹
      skeleton.json           ← 骨骼拓扑：关节、骨骼、链、参数链
      preset_schema.json      ← 预设 schema（随骨架自动派生）
      actions3d/              ← 3D 动作定义（每动作一个文件）
        walk3d.json
        run3d.json
        idle3d.json
        jump3d.json
    three_head_dragon/        ← 三头飞龙（同上结构）
  presets/                    ← 体型预设（按物种分文件夹）
    human/
      model_male.json
      model_female.json
      ...
    three_head_dragon/
      three_head_dragon_default.json
```

## API

| 端点 | 说明 |
|---|---|
| `GET /api/species` | 扫描 species/ 下所有含 skeleton.json 的文件夹，自动发现 actions/ |
| `GET /api/species/<id>` | 返回 skeleton.json + actions/ 下所有动作 |
| `POST /api/species` | 创建物种文件夹 + skeleton.json + actions/ |
| `PUT /api/species/<id>` | 更新 skeleton.json |
| `DELETE /api/species/<id>` | 删除整个物种文件夹 |
| `GET /api/skeletons` | 预设列表 |
| `GET /api/skeletons/<id>` | 预设详情（自动合并物种骨骼数据） |
| `POST /api/skeletons/<id>/render` | 骨架预览 |
| `GET /api/motions` | 从所有物种的 actions/ 扫描动作列表 |
| `POST /api/motions/<id>/render` | 动作预览 |
| `GET /api/skeleton3d/<preset_id>?yaw=45` | **3D 骨架**任意视角 PNG（支持 `yaw`/`pitch`/`dist`/`zoom`） |
| `GET /api/motion3d/<action_id>?yaw=45&gif=1` | **3D 动作**任意视角 PNG/GIF（支持 `yaw`/`pitch`/`dist`/`zoom`/`frame`） |

**3D 相机参数**（角度 + 距离，透视投影）：
- `yaw` 水平角（0-360，绕 Y 旋转：0=front，90=side，180=back）
- `pitch` 俯仰角（-60~60，绕 X 旋转，俯视/仰视）
- `dist` 相机距离（200-1500，透视近大远小）
- `zoom` 缩放倍率（0.5-2）

前端「🧊 3D 预览」标签页提供 4 个滑块实时调节并自动渲染。

## 3D 架构（阶段 1/2 — 3D 坐标 + 投影）

原 2D 多视图架构（每视图独立坐标/偏移）有冗余与不一致问题。
新架构引入 **3D 坐标系 + 正交投影**，一套坐标、任意视角。

```
数据层（3D）
  species/human/actions3d/*.json   ← 3D 动作（offsets3d 用 x/y/z 轴）
  presets/*.json（front/side 坐标） ← 自动合成 3D 坐标
        ↓ build_skeleton_3d()       （x/y 取 front，z 取 side 前后深度）
3D 骨架 {joint: [x,y,z]}
        ↓ pose_3d()                 3D 空间应用 offsets3d + 3D IK
3D 姿势
        ↓ project()                 绕 Y 轴旋转 + 正交投影（yaw 任意角度）
2D 屏幕坐标 → render_pose() → PNG/GIF
```

- `assetslab/skeleton3d.py`：3D 骨架构建、投影、3D 动作引擎（pose_3d）、3D 两骨 IK（pole 定弯曲）
- 3D 动作：`offsets3d[关节] = {x/y/z 偏移表达式}`，信号 DSL 与 2D 引擎共用（`motion._eval`）
- 3D IK：`ik3d` 保持骨长，pole 默认 +z（膝朝前）/ -z（肘朝后），超长自动 clamp 脚微离地
- **任意视角**：yaw=0→front，90→side，180→back，任意角度→斜视角
- 2D 引擎（`motion.py`）保持零改动，现有动作/验证管线不受影响

阶段 2 已验证：`walk3d` 演示动作在任意视角下前后迈步、抬脚、摆臂协调。
阶段 3（计划）：3D 动作完全替换 2D（offsets_3d 全面化 + 前端任意视角 UI）。

## 启动

```bash
cd assetslab/web && npm install && npm run build
python assetslab/server.py --port 8765
```

## 架构约束（强制 — 禁止硬编码，数据驱动）

> 本约定为强制约束。任何代码新增/修改都必须遵守，违者视为架构违规。

**核心原则：数据在 JSON，逻辑在引擎，参数化渲染。**
- 动作 / 骨架 / 体型 / 约束 / 相机 **全部由 JSON 定义**，程序只负责读取并渲染，**禁止在代码中硬编码**任何：
  - 具体关节名（如 `ankle_left`、`heel_left`、`wrist_left`）—— 关节/链/对一律从骨架 JSON 的 `constraints` 读取
  - 解剖方向 / 肢体逻辑（如"膝盖朝前"、"脚掌跟踝"）—— 一律数据化为 `constraints.joint_direction` / `rigid_chains` 等
  - 物种 / 动作路径（如 `human`、`actions3d`）—— 从 `species/` 扫描
  - 数值常量（画布中心、地面 Y、相机默认值）—— 从 preset 的 `canvas` 读取

**JSON 多层（数据归属）**
| 层 | 数据 | 存放 |
|----|------|------|
| 物种 skeleton.json | 拓扑、`bones_3d`、约束（`rigid_chains`/`symmetry3d`/`coordination`/`joint_direction`/...） | `species/<id>/skeleton.json` |
| 体型 preset | `positions_3d`（3D 坐标）、`canvas`（画布/地面/中心） | `presets/<id>.json` |
| 动作 action | `offsets3d`、`root3d`、`ik3d`、`signals`、`params` | `species/<id>/actions3d/<id>.json` |

**引擎只读数据 + 参数**
- 渲染 = 读取（骨架 JSON + 动作 JSON + 动作参数 + 体型参数 + 相机参数 `yaw/pitch/dist/zoom`）→ 计算 → 输出
- 引擎不产生新数据语义；若 JSON 缺字段，应回退/报错，**不得在代码里补默认人类值**

**验证也数据驱动**
- `verify_motions3d.py` 的检查项（对称对、顺拐对、刚性跟随、脚着地）全部从骨架 `constraints` 读取，禁止硬编码关节名

**已知技术债（待清理，不得新增）**
- `render.py` 的 `torso_outline_*`（2D 遗留的人类躯干轮廓）与旧 `front_*_pose` 死代码 —— 属旧 2D 层，3D 渲染（`skeleton3d.py`）不使用；后续应删除或数据化


