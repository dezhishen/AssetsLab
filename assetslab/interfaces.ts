// =========================================================================
// AssetsLab — 数据驱动角色素材管线 · 类型声明
// =========================================================================
// 本文档定义项目的核心数据结构，不关心实现细节，只声明"是什么"。
// 命名规范：snake_case（与 JSON 存储一致），面向人类和 AI 的可读性。
// =========================================================================

// -------------------------------------------------------------------------
// 基础类型
// -------------------------------------------------------------------------

/** 关节名称，如 "head", "elbow_left" */
type JointName = string

/** 一条骨骼：两个关节的连接 */
type Bone = [JointName, JointName]

/** 2D 坐标 */
type Position = [x: number, y: number]

/** 视图方向 */
type View = 'front' | 'side' | 'back'

/** 动画阶段（累积叠加） */
type MotionStage = 'skeleton' | 'legs' | 'pelvis' | 'arms'

// -------------------------------------------------------------------------
// 1. 物种（Species）— 纯骨骼拓扑，不包含体型/坐标
//    存储位置：species/<id>/skeleton.json
// -------------------------------------------------------------------------

interface SpeciesSkeleton {
  species_id: string                   // 唯一标识，如 "human"
  schema: 'assetslab_species_v1'       // 格式版本
  title: string                        // 显示名称，如 "人类骨骼拓扑"
  description: string                  // 描述文本

  /** 关节分组：按身体部位组织的关节名称列表 */
  joints: JointGroups

  /** 骨骼连接：每个视图下的骨骼对列表 */
  bones: BoneMap

  /** 关节链：层级关节序列，如脊柱链、手臂链 */
  chains: ChainMap

  /** 参数链：可调体型参数 → 受影响关节的映射（只有结构，没有数值） */
  param_chains: Record<string, ParamChain>

  /** 躯干关节（受 torso 继承影响的关节） */
  torso_joints: JointName[]

  /** 上半身关节 */
  upper_joints: JointName[]
}

/** 关节分组 */
interface JointGroups {
  centerline: JointName[]        // 中轴线：head → jaw → neck → ... → pelvis
  left_arm: JointName[]          // 左臂链
  right_arm: JointName[]         // 右臂链
  left_leg: JointName[]          // 左腿链
  right_leg: JointName[]         // 右腿链
  clavicles?: JointName[]        // 锁骨
  ribs?: JointName[]             // 肋骨
  /** 别名映射：旧名称 → 标准名称，如 "left_hand" → "palm_left" */
  aliases: Record<JointName, JointName>
}

/** 骨骼连接表 */
interface BoneMap {
  front: Bone[]                  // 正面视图骨骼
  side: Bone[]                   // 侧面视图骨骼
  back: Bone[]                   // 背面视图骨骼
}

/** 关节链表 */
interface ChainMap {
  spine: JointName[]             // 脊柱链
  arm_left: JointName[]          // 左臂链
  arm_right: JointName[]         // 右臂链
  leg_left: JointName[]          // 左腿链
  leg_right: JointName[]         // 右腿链
}

/** 参数链：描述一个体型参数影响哪些关节 */
interface ParamChain {
  joints: JointName[]            // 受影响的关节列表
  param: string                  // 对应的参数名，如 "head_scale"
  anchor: string                 // 锚点关节名或 "center" / "bottom"
}

// -------------------------------------------------------------------------
// 2. 预设（Preset）— 基于物种的具体体型
//    存储位置：presets/<id>.json
//    运行时从物种合并 bones / chains / joints / param_chains
// -------------------------------------------------------------------------

interface Preset {
  preset_id: string                // 唯一标识，如 "standard", "female"
  schema: 'assetslab_preset_v3'    // 格式版本
  title: string                    // 显示名称
  description: string              // 描述
  species: string                  // 引用的物种 ID，如 "human"

  /** 头部显示半径（像素） */
  head_radius: number

  /** 画布设置 */
  canvas: Canvas

  /** 体型参数规格（带范围/步进/标签） */
  params: Record<string, ParamSpec>

  /** 体型参数当前值 */
  body: Record<string, number>

  /** 各视图下的关节坐标 */
  positions: JointPositions
}

/** 画布 */
interface Canvas {
  width: number                   // 画布像素宽
  height: number                  // 画布像素高
  floor_y: number                 // 地面 Y 坐标
}

/** 单个体型参数规格 */
interface ParamSpec {
  default: number                 // 默认值
  min: number                     // 最小值
  max: number                     // 最大值
  step: number                    // 步进
  label: string                   // 中文标签
  desc: string                    // 描述
}

/** 关节坐标：按视图索引 */
interface JointPositions {
  front: Record<JointName, Position>
  side: Record<JointName, Position>
  back: Record<JointName, Position>
}

// -------------------------------------------------------------------------
// 3. 动作（Motion / Action）— 动画定义
//    存储位置：species/<id>/actions/<motion_id>.json
// -------------------------------------------------------------------------

interface Motion {
  schema: 'assetslab_motion_v1'    // 格式版本
  motion_id: string                // 唯一标识，如 "walk", "run"
  title: string                    // 显示名称
  description: string              // 描述
  species: string                  // 所属物种 ID
  frame_count: number              // 循环帧数（通常 8）

  /** 可调参数（步幅、骨盆起伏、摆臂等） */
  params: Record<string, MotionParam>

  /** 信号表达式：命名波形，用数学表达式描述关节随时间的变化 */
  signals: Record<string, SignalExpr>

  /** 根运动偏移（每帧） */
  root: {
    dx: SignalExpr                 // X 方向位移
    dy: SignalExpr                 // Y 方向位移
  }

  /** 关节偏移：按视图 × 阶段 × 关节的偏移定义 */
  offsets: Record<View, Record<string, Record<JointName, SignalExpr>>>

  /** 帧选择器：决定哪条腿在前 / 前景 */
  selectors: Record<string, SignalExpr>

  /** IK 约束组 */
  ik?: Record<View, Record<string, IKGroup>>
}

/** 动作参数（与体型参数结构相同） */
interface MotionParam {
  default: number
  min: number
  max: number
  label: string
}

/**
 * 信号表达式：描述一个随时间变化的值。
 *
 * 可以是简单值：
 *   { "phase": true }              — 引用 phase 信号
 *   { "param": "stride" }          — 引用参数值
 *   3.14                            — 常量
 *
 * 也可以是运算符：
 *   { "sin": SignalExpr }          — 正弦
 *   { "cos": SignalExpr }          — 余弦
 *   { "neg": SignalExpr }          — 取反
 *   { "rect": SignalExpr }         — 整流（取正值）
 *   { "mul": SignalExpr[] }        — 相乘
 *   { "add": SignalExpr[] }        — 相加
 *   { "table": number[][] }        — 查表（相位 → 值映射）
 */
type SignalExpr = number | string | { [op: string]: SignalExpr | SignalExpr[] | number[][] | boolean }

/** IK 约束组 */
interface IKGroup {
  joints: [JointName, JointName, JointName]  // 三个关节：根、中、末
  lengths: [number, number]                   // 两段骨骼长度
  bend_dir: -1 | 1                            // 弯曲方向
}

// -------------------------------------------------------------------------
// 4. 存储布局（文件系统）
// -------------------------------------------------------------------------

/**
 * assetslab/
 *   species/
 *     <species_id>/               ← 一个物种一个文件夹
 *       skeleton.json             ← SpeciesSkeleton
 *       actions/
 *         <motion_id>.json        ← Motion (每个动作一个文件)
 *         base.json               ← 基础姿态（参考，不作为动作列出）
 *   presets/
 *     <preset_id>.json            ← Preset (每个体型预设一个文件)
 *   motions/                      ← [兼容] 旧版动作目录
 */

// -------------------------------------------------------------------------
// 5. API 响应类型
// -------------------------------------------------------------------------

/** GET /api/species 列表项 */
interface SpeciesListItem {
  id: string                       // species_id
  title: string
  description: string
  joint_count: number
  bone_count: number
  chain_count: number
  param_chain_count: number
  motions: string[]                // 动作 ID 列表
  actions: ActionSummary[]         // 动作摘要列表（含标题）
}

/** 动作摘要（列表中的简要信息） */
interface ActionSummary {
  id: string                       // motion_id
  title: string
  params: Record<string, MotionParam>
}

/** GET /api/species/<id> 详情 = SpeciesSkeleton + actions */
interface SpeciesDetail extends SpeciesSkeleton {
  actions: Motion[]                // 从 actions/ 目录自动发现
}

/** GET /api/skeletons 列表项 */
interface PresetListItem {
  id: string                       // preset_id
  title: string
  description: string
  species: string | null           // 引用的物种 ID
  is_species: boolean
  is_preset: boolean
  body: Record<string, number>
  views: View[]                    // 有坐标的视图
  motions: string[]
}

/** GET /api/skeletons/<id> 详情 = Preset + 已合并物种数据 */
interface PresetDetail extends Preset {
  bones?: BoneMap                  // 从物种合并
  chains?: ChainMap                // 从物种合并
  joints?: JointGroups             // 从物种合并
  param_chains?: Record<string, ParamChain>  // 从物种合并
}

/** GET /api/motions 列表项 */
interface MotionListItem {
  id: string                       // motion_id
  title: string
  description: string
  species: string                  // 所属物种
  params: Record<string, MotionParam>
  has_ik: boolean
}

/** 骨架/动作渲染返回 */
interface RenderResult {
  ok: boolean
  data_url?: string                // base64 PNG
  frame?: string                   // base64 PNG (动作单帧)
  error?: string
}

// -------------------------------------------------------------------------
// 6. 运行时骨架（合并后的内部表示，仅供理解渲染流程）
// -------------------------------------------------------------------------

/**
 * 运行时骨架 = Preset + Species 合并后的完整数据结构。
 * preset.positions 提供关节坐标，species.bones 提供骨骼连接。
 * 这是渲染器实际使用的格式，不作为存储格式。
 */
interface RuntimeSkeleton {
  skeleton_id: string              // preset_id
  schema: string
  title: string
  description: string
  canvas: Canvas
  head_radius: number
  body: Record<string, number>
  views: JointPositions            // 从 preset.positions 来
  bones: BoneMap                   // 从 species.bones 来
  params: Record<string, ParamSpec>
  param_chains: Record<string, ParamChain>
  chains: ChainMap
  torso: Record<View, Record<JointName, number>>  // 躯干继承权重
  arm_chains: ChainMap
  leg_chains: ChainMap
  upper_joints: JointName[]
}

// =========================================================================
// 关系速查
// =========================================================================
//
//   Species ────────────────── Preset
//   (骨骼拓扑)                (体型+坐标)
//   skeleton.json             presets/<id>.json
//       │                         │
//       │ species_id ←────────── species
//       │                         │
//       ├─ joints                 ├─ positions (关节坐标)
//       ├─ bones                  ├─ params (体型参数规格)
//       ├─ chains                 ├─ body (体型参数值)
//       ├─ param_chains           ├─ head_radius
//       └─ torso_joints           └─ canvas
//       │
//       └─ actions/               Motion
//          walk.json              (动画)
//          run.json                   │
//          ...                    species ← 所属物种
//                                     │
//                                 ├─ params (可调参数)
//                                 ├─ signals (波形表达式)
//                                 ├─ offsets (关节偏移)
//                                 ├─ selectors (帧选择器)
//                                 └─ ik (IK约束)
//
//   运行时合并：Preset + Species → RuntimeSkeleton
//   渲染时：RuntimeSkeleton + Motion → 动画帧
// =========================================================================
