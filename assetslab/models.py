# =========================================================================
# AssetsLab — 数据驱动角色素材管线 · Python 类型声明
# =========================================================================
# 本文档使用 typing.TypedDict 声明项目核心数据结构。
# 对应前端类型声明：assetslab/interfaces.ts（同名结构，双端一致）。
# 命名规范：snake_case（与 JSON 存储一致）。
# 作用：mypy 静态检查、编辑器补全、AI/人类阅读的数据模型文档。
# =========================================================================

from __future__ import annotations

from typing import Dict, List, Literal, NotRequired, Tuple, TypedDict

# -------------------------------------------------------------------------
# 基础类型别名
# -------------------------------------------------------------------------

#: 关节名称，如 "head", "elbow_left"
JointName = str

#: 一条骨骼：两个关节的连接
Bone = Tuple[JointName, JointName]

#: 2D 坐标
Position = Tuple[float, float]

#: 视图方向
View = Literal["front", "side", "back"]

#: 动画阶段（累积叠加）
MotionStage = Literal["skeleton", "legs", "pelvis", "arms"]

# -------------------------------------------------------------------------
# 1. 物种（Species）— 纯骨骼拓扑，不包含体型/坐标
#    存储位置：species/<id>/skeleton.json
# -------------------------------------------------------------------------


class SpeciesSkeleton(TypedDict):
    """物种骨骼拓扑。

    species_id: 唯一标识，如 "human"
    schema: 格式版本 "assetslab_species_v1"
    title: 显示名称
    description: 描述文本
    joints: 关节分组（按身体部位组织的关节名称列表）
    bones: 骨骼连接（每个视图下的骨骼对列表）
    chains: 关节链（层级关节序列）
    param_chains: 参数链（可调体型参数 → 受影响关节映射，只有结构没有数值）
    torso_joints: 躯干关节（受 torso 继承影响的关节）
    upper_joints: 上半身关节
    """

    species_id: str
    schema: str
    title: str
    description: str
    joints: "JointGroups"
    bones: "BoneMap"
    chains: "ChainMap"
    param_chains: Dict[str, "ParamChain"]
    torso_joints: List[JointName]
    upper_joints: List[JointName]


class JointGroups(TypedDict):
    """关节分组。

    centerline: 中轴线 head → jaw → neck → ... → pelvis
    left_arm / right_arm: 手臂链
    left_leg / right_leg: 腿链
    clavicles: 锁骨（可选）
    ribs: 肋骨（可选）
    aliases: 别名映射 旧名称 → 标准名称（如 "left_hand" → "palm_left"）
    """

    centerline: List[JointName]
    left_arm: List[JointName]
    right_arm: List[JointName]
    left_leg: List[JointName]
    right_leg: List[JointName]
    clavicles: NotRequired[List[JointName]]
    ribs: NotRequired[List[JointName]]
    aliases: Dict[JointName, JointName]


class BoneMap(TypedDict):
    """骨骼连接表：每个视图下的骨骼对列表。"""

    front: List[Bone]
    side: List[Bone]
    back: List[Bone]


class ChainMap(TypedDict):
    """关节链表：层级关节序列。

    spine: 脊柱链
    arm_left / arm_right: 手臂链
    leg_left / leg_right: 腿链
    """

    spine: List[JointName]
    arm_left: List[JointName]
    arm_right: List[JointName]
    leg_left: List[JointName]
    leg_right: List[JointName]


class ParamChain(TypedDict):
    """参数链：描述一个体型参数影响哪些关节。

    joints: 受影响的关节列表
    param: 对应的参数名，如 "head_scale"
    anchor: 锚点关节名或 "center" / "bottom"
    """

    joints: List[JointName]
    param: str
    anchor: str


# -------------------------------------------------------------------------
# 2. 预设（Preset）— 基于物种的具体体型
#    存储位置：presets/<id>.json
#    运行时从物种合并 bones / chains / joints / param_chains
# -------------------------------------------------------------------------


class Canvas(TypedDict):
    """画布设置。"""

    width: int      # 画布像素宽
    height: int     # 画布像素高
    floor_y: int    # 地面 Y 坐标


class ParamSpec(TypedDict):
    """单个体型参数规格。"""

    default: float   # 默认值
    min: float       # 最小值
    max: float       # 最大值
    step: float      # 步进
    label: str       # 中文标签
    desc: str        # 描述


class JointPositions(TypedDict):
    """关节坐标：按视图索引。"""

    front: Dict[JointName, Position]
    side: Dict[JointName, Position]
    back: Dict[JointName, Position]


class Preset(TypedDict):
    """体型预设（基于物种的实例：体型参数 + 动作参数）。

    preset_id: 唯一标识，如 "model_male"
    schema: 格式版本 "assetslab_preset_v1"
    title / description: 显示信息
    species: 引用的物种 ID（schema 由物种派生）
    body: 体型参数当前值（调整骨骼尺寸，如 head_scale / shoulder_width）
    actions: 各动作参数覆盖（调整动作幅度，如 walk3d 的 intensity/stride）
    """

    schema: str
    preset_id: str
    title: str
    description: str
    species: str
    body: Dict[str, float]
    actions: Dict[str, Dict[str, float]]


class PresetSummary(TypedDict):
    """预设摘要（列表展示）。"""

    preset_id: str
    title: str
    description: str
    species: str


# -------------------------------------------------------------------------
# 3. 动作（Motion / Action）— 动画定义
#    存储位置：species/<id>/actions/<motion_id>.json
# -------------------------------------------------------------------------


class MotionParam(TypedDict):
    """动作参数（与体型参数结构相同）。"""

    default: float
    min: float
    max: float
    label: str


# 信号表达式：递归类型。可以是常量 / 引用 / 运算符。
# 由于 Python TypedDict 不支持直接递归，使用宽松类型 + 文档说明。
# {
#   "phase": true                — 引用 phase 信号
#   "param": "stride"            — 引用参数值
#   3.14                         — 常量
#   "sin" / "cos" / "neg" / "rect" / "mul" / "add" / "table" — 运算符
# }
SignalExpr = object  # 运行时校验，见 motion.py `_resolve_expr`


class IKGroup(TypedDict):
    """IK 约束组。"""

    joints: Tuple[JointName, JointName, JointName]  # 根、中、末三个关节
    lengths: Tuple[float, float]                    # 两段骨骼长度
    bend_dir: int                                   # 弯曲方向 -1 | 1


class Motion(TypedDict):
    """动作定义。

    schema: 格式版本 "assetslab_motion_v1"
    motion_id: 唯一标识，如 "walk", "run"
    title / description: 显示信息
    species: 所属物种 ID
    frame_count: 循环帧数（通常 8）
    params: 可调参数（步幅、骨盆起伏、摆臂等）
    signals: 信号表达式，命名波形
    root: 根运动偏移（每帧 dx/dy）
    offsets: 关节偏移 视图 → 阶段 → 关节 → 信号表达式
    selectors: 帧选择器（决定哪条腿在前 / 前景）
    ik: IK 约束组
    """

    schema: str
    motion_id: str
    title: str
    description: str
    species: str
    frame_count: int
    params: Dict[str, MotionParam]
    signals: Dict[str, SignalExpr]
    root: Dict[str, SignalExpr]
    offsets: Dict[View, Dict[str, Dict[JointName, SignalExpr]]]
    selectors: Dict[str, SignalExpr]
    ik: NotRequired[Dict[View, Dict[str, IKGroup]]]


# -------------------------------------------------------------------------
# 4. API 响应类型
# -------------------------------------------------------------------------


class ActionSummary(TypedDict):
    """动作摘要（列表中的简要信息）。"""

    id: str                                   # motion_id
    title: str
    params: Dict[str, MotionParam]


class SpeciesListItem(TypedDict):
    """GET /api/species 列表项。"""

    id: str
    title: str
    description: str
    joint_count: int
    bone_count: int
    chain_count: int
    param_chain_count: int
    motions: List[str]                        # 动作 ID 列表
    actions: List[ActionSummary]              # 动作摘要列表


class SpeciesDetail(SpeciesSkeleton):
    """GET /api/species/<id> 详情 = SpeciesSkeleton + actions。

    actions: 从 actions/ 目录自动发现的动作列表
    """

    actions: List["Motion"]


class PresetListItem(TypedDict):
    """GET /api/skeletons 列表项。"""

    id: str
    title: str
    description: str
    species: str | None                        # 引用的物种 ID
    is_species: bool
    is_preset: bool
    body: Dict[str, float]
    views: List[View]                          # 有坐标的视图
    motions: List[str]


class PresetDetail(Preset):
    """GET /api/skeletons/<id> 详情 = Preset + 已合并物种数据。"""

    bones: NotRequired[BoneMap]                # 从物种合并
    chains: NotRequired[ChainMap]              # 从物种合并
    joints: NotRequired[JointGroups]           # 从物种合并
    param_chains: NotRequired[Dict[str, ParamChain]]  # 从物种合并


class MotionListItem(TypedDict):
    """GET /api/motions 列表项。"""

    id: str
    title: str
    description: str
    species: str                               # 所属物种
    params: Dict[str, MotionParam]
    has_ik: bool


class RenderResult(TypedDict):
    """骨架/动作渲染返回。"""

    ok: bool
    data_url: NotRequired[str]                 # base64 PNG
    frame: NotRequired[str]                    # base64 PNG (动作单帧)
    error: NotRequired[str]


# -------------------------------------------------------------------------
# 5. 运行时骨架（合并后的内部表示，仅供理解渲染流程）
# -------------------------------------------------------------------------


class RuntimeSkeleton(TypedDict):
    """运行时骨架 = Preset + Species 合并后的完整数据结构。

    preset.positions 提供关节坐标，species.bones 提供骨骼连接。
    这是渲染器实际使用的格式，不作为存储格式。
    """

    skeleton_id: str                           # preset_id
    schema: str
    title: str
    description: str
    canvas: Canvas
    head_radius: float
    body: Dict[str, float]
    views: JointPositions                      # 从 preset.positions 来
    bones: BoneMap                             # 从 species.bones 来
    params: Dict[str, ParamSpec]
    param_chains: Dict[str, ParamChain]
    chains: ChainMap
    torso: Dict[View, Dict[JointName, float]]  # 躯干继承权重
    arm_chains: Dict[str, Dict[JointName, List[JointName]]]
    leg_chains: Dict[str, Dict[JointName, List[JointName]]]
    upper_joints: List[JointName]


# =========================================================================
# 关系速查
# =========================================================================
#
#   Species ────────────────── Preset
#   (骨骼拓扑)                (体型+坐标)
#   skeleton.json             presets/<id>.json
#       │                         │
#       │ species_id ←────────── species
#       │                         │
#       ├─ joints                 ├─ positions (关节坐标)
#       ├─ bones                  ├─ params (体型参数规格)
#       ├─ chains                 ├─ body (体型参数值)
#       ├─ param_chains           ├─ head_radius
#       └─ torso_joints           └─ canvas
#       │
#       └─ actions/               Motion
#          walk.json              (动画)
#          run.json                   │
#          ...                    species ← 所属物种
#                                     │
#                                 ├─ params (可调参数)
#                                 ├─ signals (波形表达式)
#                                 ├─ offsets (关节偏移)
#                                 ├─ selectors (帧选择器)
#                                 └─ ik (IK约束)
#
#   运行时合并：Preset + Species → RuntimeSkeleton
#   渲染时：RuntimeSkeleton + Motion → 动画帧
# =========================================================================
