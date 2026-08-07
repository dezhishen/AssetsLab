#!/usr/bin/env python3
"""AssetsLab — 3D 骨架数据 + 投影引擎（阶段 1）。

背景：原架构是"2D 多视图"（每个视图独立存坐标 + 独立动作偏移），
同一关节在 front/side/back 各有一份坐标，冗余且易不一致。
本模块引入 3D 坐标系（x 左右 / y 上下 / z 前后），
从现有 2D 数据【自动合成】3D 坐标，再通过【正交投影】得到任意视角。

数据流：
    2D preset (positions front/side/back)
        ↓ build_skeleton_3d() 自动合成
    3D 骨架 {joint: [x, y, z]} + 3D 骨列表
        ↓ project(joints3d, yaw) 绕 Y 轴旋转 + 正交投影
    2D 屏幕坐标 {joint: (sx, sy)}
        ↓ render_view() 复用 render.py 绘制
    PNG / 帧

阶段 1 范围：3D 骨架数据 + 任意视角（yaw）骨架渲染。
现有 2D 引擎 / 动作 / 验证管线保持零改动。
阶段 2 再对动作做 3D 化（offsets_3d + 3D IK + 动态 z 排序）。
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from assetslab.models import Preset, SpeciesSkeleton, View

PKG_ROOT = Path(__file__).resolve().parent
PRESETS_ROOT = PKG_ROOT / "presets"
SPECIES_ROOT = PKG_ROOT / "species"

# 视图 → 是否水平镜像（back 从背后看，x 反向）
_VIEW_FLIP = {"front": 1, "back": -1}

# 3D 中线（side 视图 x 基准，用于把"前后"换算成 z 深度）
SIDE_MID = 480.0


def load_preset(preset_id: str, species_id: str | None = None) -> Preset:
    """读取预设：优先 presets/<species>/<id>.json，找不到则跨物种子目录搜索。"""
    path: Path | None = None
    if species_id:
        cand = PRESETS_ROOT / species_id / f"{preset_id}.json"
        if cand.is_file():
            path = cand
    if path is None:
        matches = sorted(PRESETS_ROOT.glob(f"*/{preset_id}.json"))
        if matches:
            path = matches[0]
    if path is None:
        cand = PRESETS_ROOT / f"{preset_id}.json"  # 兼容平铺
        if cand.is_file():
            path = cand
    if path is None:
        raise FileNotFoundError(f"preset not found: {preset_id}")
    with open(path) as f:
        return __import__("json").load(f)


def load_species(species_id: str) -> SpeciesSkeleton:
    with open(SPECIES_ROOT / species_id / "skeleton.json") as f:
        return __import__("json").load(f)


def load_default(species_id: str) -> dict:
    """读取物种默认参数（species/<id>/default.json）：默认姿态 + 体型参数。"""
    with open(SPECIES_ROOT / species_id / "default.json") as f:
        return __import__("json").load(f)


def _limb_side_map(chains: dict) -> dict[str, tuple[str, str]]:
    """3D 关节名 → (side_front_name, side_rear_name)。

    自动推导：左肢（*_left）映射到 side 的 front_*（近侧），
    右肢（*_right）映射到 side 的 rear_*（远侧）；躯干关节同名。
    返回 {joint3d: (front_name, rear_name)}。
    """
    out: dict[str, tuple[str, str]] = {}
    for chain in chains.values():
        for j in chain:
            if j.endswith("_left"):
                base = j[:-5]  # 去掉 _left
                out[j] = (f"front_{base}", f"rear_{base}")
            elif j.endswith("_right"):
                base = j[:-6]
                out[j] = (f"front_{base}", f"rear_{base}")
            else:
                out[j] = (j, j)  # 躯干：side 同名（如 neck, chest）
    return out


def apply_proportions_3d(joints3d: dict[str, list[float]],
                         proportions: dict | None,
                         species: dict,
                         head_radius: float = 24.0) -> dict[str, list[float]]:
    """在 3D 空间应用体型参数（param_chains 数据驱动，无硬编码关节名）。

    每个体型参数对应 species param_chains 里一条或多条链（param 字段匹配），
    按链的 anchor 语义处理：
      - anchor == "center"         → 绕脊柱中线（spine 链末端）x 缩放，链下游跟随平移
      - anchor == "bottom"         → 关节向上生长（如 head_scale）
      - anchor 是脊柱链内关节      → 脊柱段缩放：段上端=链内最靠上的脊柱关节，
                                    段上端及以上（含 head/上肢）整体上移
      - anchor 是普通关节          → 链内关节相对锚点沿 3 维缩放（肢体/颈/胸骨段）
    未在 param_chains 定义的参数一律忽略（数据驱动：没定义就不变）。
    返回新的 joints3d（不修改入参）。
    """
    out: dict[str, list[float]] = {k: list(v) for k, v in joints3d.items()}
    p = {k: float(v) for k, v in (proportions or {}).items() if v is not None}
    upper = species.get("upper_joints", [])
    chains = species.get("chains", {})
    pc = species.get("param_chains", {})
    spine = list(chains.get("spine", []))
    spine_set = set(spine)

    for param, scale in p.items():
        if scale == 1.0:
            continue
        for c in [c for c in pc.values() if c.get("param") == param]:
            anchor = c.get("anchor")
            joints = [j for j in c.get("joints", []) if j in out]
            if not joints:
                continue
            if anchor == "center":
                if not spine or spine[-1] not in out:
                    continue
                cx = out[spine[-1]][0]
                moved: dict[str, float] = {}
                for j in joints:
                    old = out[j][0]
                    out[j][0] = cx + (old - cx) * scale
                    moved[j] = out[j][0] - old
                # 下游跟随：链中位于该关节之后的关节一并平移（BFS，避免迭代中改 dict）
                queue = list(moved.items())
                while queue:
                    j, dx = queue.pop(0)
                    for chain in chains.values():
                        if j in chain:
                            for nxt in chain[chain.index(j) + 1:]:
                                if nxt in out and nxt not in moved:
                                    out[nxt][0] += dx
                                    moved[nxt] = dx
                                    queue.append((nxt, dx))
            elif anchor == "bottom":
                for j in joints:
                    out[j][1] -= head_radius * (scale - 1.0)
            elif anchor in spine_set and anchor in out:
                ai = spine.index(anchor)
                top = min((j for j in joints if j in spine_set), key=spine.index, default=None)
                if top is None or top == anchor:
                    continue
                dy = (out[top][1] - out[anchor][1]) * (scale - 1.0)
                for n in upper + ["head"]:
                    if n in out and (n not in spine_set or spine.index(n) < ai):
                        out[n][1] += dy
            elif anchor in out:
                a = out[anchor]
                for j in joints:
                    for k in range(3):
                        out[j][k] = a[k] + (out[j][k] - a[k]) * scale
    return out



def build_skeleton_3d(species_id: str = "human", body: dict | None = None) -> dict:
    """读取 JSON 定义的 3D 骨架（数据驱动，基于物种默认参数）。

    基础姿态来自 species/<id>/default.json 的 ``positions_3d``（默认参数，数据即定义）；
    ``body`` 提供体型参数覆盖（可选），在 3D 空间应用 param_chains 缩放。

    返回 {"joints": {joint3d: [x, y, z]}, "bones": [[a,b],...], ...}
    """
    default = load_default(species_id)
    species = load_species(species_id)

    # 3D 坐标：物种默认参数（JSON 显式定义）
    joints3d: dict[str, list[float]] = {
        j: [float(v[0]), float(v[1]), float(v[2])]
        for j, v in default.get("positions_3d", {}).items()
    }
    if body:
        joints3d = apply_proportions_3d(joints3d, body, species,
                                        float(default.get("head_radius", 24.0)))

    # 3D 骨列表：JSON 显式定义优先
    bones_3d: list[list[str]] = []
    if species.get("bones_3d"):
        bones_3d = [list(b) for b in species["bones_3d"]]
    else:
        for chain in species["chains"].values():
            for a, b in zip(chain, chain[1:]):
                if [a, b] not in bones_3d:
                    bones_3d.append([a, b])

    # 画布中心 / 地面：从默认参数 canvas 定义读（数据驱动，不硬编码）
    canvas_cfg = default.get("canvas", {})
    center = [float(canvas_cfg.get("width", 960)) / 2.0,
              float(canvas_cfg.get("height", 600)) / 2.0, 0.0]
    floor_y = float(canvas_cfg.get("floor_y", 470.0))

    # 刚性链：从物种 constraints.rigid_chains 读（数据驱动）
    rigid_chains = (species.get("constraints", {})
                    .get("rigid_chains", {}).get("chains", []))

    return {
        "joints": joints3d,
        "bones": bones_3d,
        "chains": species.get("chains", {}),
        "view2d": _build_view2d(_limb_side_map(species.get("chains", {})),
                                species.get("chains", {}), default),
        "center": center,
        "floor_y": floor_y,
        "rigid_chains": rigid_chains,
        "head_radius": float(default.get("head_radius", 24.0)),
        "species_id": species_id,
        "follow_chains": species.get("follow_chains", {}),
        "follow_config": species.get("follow_config", {}),
        "fk_tree": species.get("fk_tree", {}),
        "fk_local": _build_fk_local(joints3d, species.get("fk_tree", {})),
        "constraints": species.get("constraints", {}),
    }


def _build_fk_local(joints3d: dict, fk_tree: dict) -> dict[str, list[float]]:
    """基准姿态下每关节相对父的向量（FK 局部偏移；根无父则不包含）。"""
    out: dict[str, list[float]] = {}
    for j, p in fk_tree.items():
        if p is not None and p in joints3d and j in joints3d:
            out[j] = [joints3d[j][k] - joints3d[p][k] for k in range(3)]
    return out


def _synthesize_3d(preset: Preset, species: SpeciesSkeleton) -> dict[str, list[float]]:
    """兼容回退：从 2D front(x,y) + side(前后深度) 合成 3D 坐标。"""
    front = preset["positions"]["front"]
    side = preset["positions"]["side"]
    side_map = _limb_side_map(species.get("chains", {}))
    out: dict[str, list[float]] = {}
    for j, (fx, fy) in front.items():
        front_name, _ = side_map.get(j, (j, j))
        sz = side.get(front_name, [SIDE_MID, 0.0])[0]
        out[j] = [fx, fy, sz - SIDE_MID]
    return out


def chains_flat(chains: dict) -> set[str]:
    out: set[str] = set()
    for lst in chains.values():
        out.update(lst)
    return out


def _build_view2d(side_map: dict, chains: dict, preset: dict) -> dict:
    """构建 3D 关节 → 各 2D 视图关节名 的映射（供投影后对齐绘制）。

    view2d[view][joint3d] = 2d 关节名（front/side/back 各自的名字）。
    """
    pos = preset.get("positions", {})
    view2d: dict[str, dict[str, str]] = {"front": {}, "side": {}, "back": {}}
    flat = chains_flat(chains)
    for j in flat:
        if j in pos.get("front", {}):
            view2d["front"][j] = j
        front_name, rear_name = side_map.get(j, (j, j))
        if front_name in pos.get("side", {}):
            view2d["side"][j] = front_name
        # back：rearr 前后 + left/right
        for suf in ("_left", "_right"):
            bj = f"rear_{j}" if suf in j else j
            if bj in pos.get("back", {}):
                view2d["back"][j] = bj
    return view2d


# --------------------------------------------------------------------------
# 投影（3D 相机：角度 + 距离）
# --------------------------------------------------------------------------

# 默认画布中心（未指定时用标准 960x600；build_skeleton_3d 从 preset canvas 读真实值）
CAM_CX, CAM_CY = 480.0, 300.0
# 画布尺寸（与 render.py 一致；自动适配填满用）
_CANVAS_W, _CANVAS_H = 960.0, 600.0
# 骨架中心（相机坐标系原点；= 画布中心时正交投影精确还原 2D 坐标）
_CENTER = (480.0, 300.0, 0.0)


def project(joints3d: dict[str, list[float]], yaw_deg: float = 0.0) -> dict[str, tuple[float, float]]:
    """兼容：绕 Y 轴旋转 yaw 后正交投影（不透视）。返回 {joint: (sx, sy)}。"""
    return project3d(joints3d, yaw_deg=yaw_deg, pitch_deg=0.0, distance=1e9)


def project3d(joints3d: dict[str, list[float]], yaw_deg: float = 0.0,
              pitch_deg: float = 0.0, distance: float = 600.0,
              zoom: float = 1.0, center: tuple[float, float, float] | None = None,
              pan_x: float = 0.0, pan_y: float = 0.0,
              ) -> dict[str, tuple[float, float]]:
    """透视相机投影：yaw（水平角）+ pitch（俯仰角）+ distance（距离）+ pan（平移）。

    - 相机沿视线看向骨架中心（默认画布中心，可传 preset 的 center），先绕 Y 再绕 X。
    - 透视除法：近大远小。distance 越小 → 相机越近 → 透视越强（放大）。
    - zoom 额外缩放（焦距倍率），distance 很大时退化为正交（≈现有 front/side）。
    - pan_x/pan_y：相机观察点平移（像素），等价于移动相机位置/画面平移。
    返回 {joint: (sx, sy)}（画布坐标）。
    """
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    cos_y, sin_y = math.cos(yaw), math.sin(yaw)
    cos_p, sin_p = math.cos(pitch), math.sin(pitch)
    cx0, cy0, cz0 = center or _CENTER
    f = max(distance, 1.0) * zoom
    out: dict[str, tuple[float, float]] = {}
    for name, (x, y, z) in joints3d.items():
        # 平移到骨架中心坐标系
        x -= cx0
        y -= cy0
        z -= cz0
        # 绕 Y：x' = x*cos + z*sin ; z' = -x*sin + z*cos
        x1 = x * cos_y + z * sin_y
        z1 = -x * sin_y + z * cos_y
        # 绕 X：y' = y*cos - z*sin ; z' = y*sin + z*cos
        y2 = y * cos_p - z1 * sin_p
        z2 = y * sin_p + z1 * cos_p
        # 透视除法（相机在 +z=distance，看向原点）+ 相机平移（pan）
        z_cam = max(distance - z2, 1.0)
        sx = cx0 + x1 * f / z_cam + pan_x
        sy = cy0 + y2 * f / z_cam + pan_y
        out[name] = (sx, sy)
    return out


# --------------------------------------------------------------------------
# 3D 两骨 IK
# --------------------------------------------------------------------------


def ik3d(hip: list[float], ankle: list[float], l1: float, l2: float,
         pole: tuple[float, float, float] = (0.0, 0.0, 1.0),
         bend_factor: float = 0.99) -> tuple[list[float], list[float]]:
    """3D 两骨 IK：求 mid（膝/肘）使 |hip-mid|=l1、|mid-ankle|=l2。

    pole 决定弯曲方向（默认 +z 朝前，膝盖朝前弯曲）。
    返回 (mid, clamp 后的 ankle)——超长时踝被拉回保持腿长（脚微离地）。
    """
    hip = [float(v) for v in hip]
    ankle = [float(v) for v in ankle]
    dx, dy, dz = ankle[0]-hip[0], ankle[1]-hip[1], ankle[2]-hip[2]
    dist = math.hypot(dx, dy, dz)
    # clamp 到可解范围（保留一点弯曲，避免伸直临界）
    lo = max(abs(l1-l2), 1e-6)
    hi = (l1 + l2) * bend_factor
    if dist > hi:
        # 超长：把末端（踝）沿 hip→踝 方向拉回，保持腿长（脚微离地）
        scale = hi / dist
        dx, dy, dz = dx*scale, dy*scale, dz*scale
        ankle = [hip[0]+dx, hip[1]+dy, hip[2]+dz]
        dist = hi
    elif dist < lo:
        dist = lo
    if dist <= 1e-6:
        return [hip[0], hip[1] - l1, hip[2]], ankle
    u = [dx/dist, dy/dist, dz/dist]
    cos_a = (l1*l1 + dist*dist - l2*l2) / (2.0 * l1 * dist)
    cos_a = max(-1.0, min(1.0, cos_a))
    sin_a = math.sqrt(max(0.0, 1.0 - cos_a*cos_a))
    # pole 投影到垂直 u 的平面
    pdot = pole[0]*u[0] + pole[1]*u[1] + pole[2]*u[2]
    v = [pole[0] - pdot*u[0], pole[1] - pdot*u[1], pole[2] - pdot*u[2]]
    vm = math.hypot(*v)
    if vm < 1e-6:  # pole 平行 u → 退化用任一垂直方向
        v = [0.0, 0.0, 1.0] if abs(u[2]) < 0.9 else [1.0, 0.0, 0.0]
        pdot = v[0]*u[0] + v[1]*u[1] + v[2]*u[2]
        v = [v[0] - pdot*u[0], v[1] - pdot*u[1], v[2] - pdot*u[2]]
        vm = math.hypot(*v) or 1.0
    v = [c / vm for c in v]
    # knee = hip + l1 * (cos_a*u + sin_a*v)
    mid = [hip[i] + l1 * (cos_a*u[i] + sin_a*v[i]) for i in range(3)]
    return mid, ankle


def _limb_ik_chain(root: str, mid: str, tip: str, skel3d: dict, pole=(0.0, 0.0, 1.0)) -> dict:
    """构建单条 3D IK 链（从 3D 骨架当前长度取 l1/l2）。"""
    j = skel3d["joints"]
    l1 = math.dist(j[root], j[mid])
    l2 = math.dist(j[mid], j[tip])
    return {"root": root, "mid": mid, "tip": tip, "l1": l1, "l2": l2, "pole": list(pole)}


def auto_ik3d_chains(skel3d: dict, legs: list[tuple[str, str, str]] | None = None,
                     arms: list[tuple[str, str, str]] | None = None) -> list[dict]:
    """从 3D 骨架自动生成 IK 链（腿膝朝前 pole=+z，臂肘朝后 pole=-z）。"""
    chains = []
    for root, mid, tip in (legs or []):
        chains.append(_limb_ik_chain(root, mid, tip, skel3d, pole=(0.0, 0.0, 1.0)))
    for root, mid, tip in (arms or []):
        chains.append(_limb_ik_chain(root, mid, tip, skel3d, pole=(0.0, 0.0, -1.0)))
    return chains


# --------------------------------------------------------------------------
# 正向运动学（FK）：关节旋转驱动（父坐标系欧拉角）
# --------------------------------------------------------------------------
# 成熟骨骼动画用“关节旋转”而非世界位移：每关节在父坐标系下旋转，
# 引擎沿父子树做 FK 链式求解。这从根本上避免“根位移把整条链顶起”的问题。


def _rot_mat(rx: float, ry: float, rz: float) -> list[list[float]]:
    """欧拉角(弧度)旋转矩阵，约定 R = Rz·Ry·Rx（先绕 x 再 y 再 z 应用）。"""
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    return [
        [cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
        [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
        [-sy, cy * sx, cy * cx],
    ]


def _mat_vec(m: list[list[float]], v: list[float]) -> list[float]:
    return [m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
            m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
            m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2]]


def _mat_mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def solve_fk3d(root_pos: list[float],
               fk_tree: dict[str, str | None],
               fk_local: dict[str, list[float]],
               rotations: dict[str, tuple[float, float, float]]) -> dict[str, list[float]]:
    """正向运动学：从根关节沿父子树，应用各关节局部欧拉角旋转。

    - ``fk_tree``: {joint: parent}，根关节 parent=None。
    - ``fk_local``: {joint: [dx,dy,dz]} 基准姿态下关节相对父的向量（根无）。
    - ``rotations``: {joint: (rx,ry,rz)} 弧度，局部坐标系欧拉角。
    返回 {joint: [x,y,z]} FK 解出的位置（根=root_pos + 根旋转影响子）。
    """
    root = next((j for j, p in fk_tree.items() if p is None), None)
    if root is None:
        raise ValueError("fk_tree 缺少根关节")
    # 拓扑序（BFS）
    order = [root]
    seen = {root}
    for j in order:
        for c, p in fk_tree.items():
            if p == j and c not in seen:
                seen.add(c)
                order.append(c)
    I = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    out: dict[str, list[float]] = {}
    R: dict[str, list[list[float]]] = {}
    for j in order:
        rj = rotations.get(j, (0.0, 0.0, 0.0))
        Mj = _rot_mat(rj[0], rj[1], rj[2])
        p = fk_tree[j]
        if p is None:
            out[j] = list(root_pos)
            R[j] = Mj
        else:
            Rp = R.get(p, I)
            v = fk_local[j]
            dv = _mat_vec(Rp, v)   # 位置用父累积旋转（自身旋转只影响子）
            out[j] = [out[p][0] + dv[0], out[p][1] + dv[1], out[p][2] + dv[2]]
            R[j] = _mat_mul(Rp, Mj)
    return out


# --------------------------------------------------------------------------
# 层级位移继承（节点跟随计算函数）
# --------------------------------------------------------------------------


def resolve_follow3d(explicit: dict[str, list[float]],
                     defined_axes: dict[str, set[int]],
                     follow_chains: dict,
                     follow_config: dict | None = None) -> dict[str, list[float]]:
    """节点跟随计算函数：求每个节点的局部位移（相对“整体”root3d 之外的部分）。

    模型：节点局部位移 = 自身显式 offset + 从父节点继承的位移 × 传递系数 factor。

    - 未显式定义 offset 的关节：沿父链递归继承父位移（× factor），
      实现“连接的其他骨骼”的带动（如骨盆横移带动胸腔、躯干带动头颈）。
    - 显式定义 offset 的关节：已定义轴用显式值，**未定义轴仍从父继承**，
      不再丢轴（修复“显式 offset 导致该关节脱离父横移、撕裂”的问题）。
    - 根关节（无父）：局部位移为 0——整体位移由动作 root3d（刚性继承给所有关节）承担。

    参数（数据驱动，定义在骨架 skeleton.json）：
      follow_chains           链名 → 关节列表（父子顺序，父在前子在后）
      follow_config[链].factor 传递系数：1.0 完全跟随（刚体链），0~1 衰减（柔性/缓冲），
                               >1 放大（如末端夸张）。缺省 1.0。
    返回 {joint: [x, y, z]}：所有在链中或显式的节点的局部位移。
    """
    fc = follow_config or {}
    parent: dict[str, str] = {}
    fac: dict[str, float] = {}
    for cname, chain in follow_chains.items():
        f = 1.0
        cfg = fc.get(cname)
        if isinstance(cfg, dict):
            f = float(cfg.get("factor", 1.0))
        for a, b in zip(chain, chain[1:]):
            if b not in parent:  # 先声明先得；同子节点多链时保持首个父
                parent[b] = a
                fac[b] = f
    memo: dict[str, list[float]] = {}

    def _resolve(j: str) -> list[float]:
        if j in memo:
            return memo[j]
        if j in parent:
            p = _resolve(parent[j])
            f = fac.get(j, 1.0)
            d = [p[0] * f, p[1] * f, p[2] * f]
        else:
            d = [0.0, 0.0, 0.0]
        # 显式 offset：已定义轴覆盖为显式值，未定义轴保留继承
        if j in explicit:
            for k in defined_axes.get(j, ()):
                d[k] = explicit[j][k]
        memo[j] = d
        return d

    nodes = set(parent) | set(explicit)
    return {j: _resolve(j) for j in nodes}


# --------------------------------------------------------------------------
# 3D 动作引擎（阶段 2 核心）
# --------------------------------------------------------------------------
# 动作在 3D 空间定义：offsets3d[关节] = {x/y/z 轴偏移表达式}，
# 引擎在 3D 求姿势 → 投影到任意视角。与 2D 引擎共用信号 DSL（motion._eval）。


def pose_3d(skel3d: dict, motion3d: dict, index: int, params: dict | None = None) -> dict[str, list[float]]:
    """在 3D 空间求一帧姿势：base_3d + offsets3d + 3D IK。返回 {joint: [x, y, z]}。"""
    from assetslab.motion import _build_signals, _eval, _resolve_params

    ctx = {
        "params": _resolve_params(motion3d, params),
        "index": index,
        "frame_count": int(motion3d.get("frame_count", 8)),
        "phase": math.tau * (index % int(motion3d.get("frame_count", 8))) / int(motion3d.get("frame_count", 8)),
        "signals": _build_signals(motion3d),
    }
    out = {name: [x, y, z] for name, (x, y, z) in skel3d["joints"].items()}
    root3d = motion3d.get("root3d", {})
    rdx = _eval(root3d.get("x", 0.0), ctx)
    rdy = _eval(root3d.get("y", 0.0), ctx)
    rdz = _eval(root3d.get("z", 0.0), ctx)
    offsets = motion3d.get("offsets3d", {})

    # —— FK 分支（关节旋转驱动；成熟骨骼动画方式）——
    # 动作用 fk3d.rotations3d 定义每关节局部欧拉角旋转，引擎做正向运动学。
    # 根位移 = 根关节 base + root3d(整体) + 根的显式 offsets3d(世界位移)。
    fk3d = motion3d.get("fk3d")
    fk_tree = skel3d.get("fk_tree") or {}
    fk_mode = bool(fk3d and fk_tree)
    if fk3d and fk_tree:
        root = fk3d.get("root")
        if root not in out:
            root = next((j for j, p in fk_tree.items() if p is None), None)
        rcomp = offsets.get(root, {}) if isinstance(offsets, dict) else {}
        root_pos = [out[root][0] + rdx + _eval(rcomp.get("x", 0.0), ctx),
                    out[root][1] + rdy + _eval(rcomp.get("y", 0.0), ctx),
                    out[root][2] + rdz + _eval(rcomp.get("z", 0.0), ctx)]
        rotations: dict[str, tuple[float, float, float]] = {}
        for j, comp in fk3d.get("rotations3d", {}).items():
            if j in fk_tree:
                rotations[j] = (_eval(comp.get("x_rot", 0.0), ctx),
                                _eval(comp.get("y_rot", 0.0), ctx),
                                _eval(comp.get("z_rot", 0.0), ctx))
        out = solve_fk3d(root_pos, fk_tree, skel3d.get("fk_local", {}), rotations)
        # FK 补充：非根关节的显式世界位移（offsets3d 仍可用于微调）
        for j, comp in (offsets or {}).items():
            if j in out and j != root:
                out[j][0] += _eval(comp.get("x", 0.0), ctx)
                out[j][1] += _eval(comp.get("y", 0.0), ctx)
                out[j][2] += _eval(comp.get("z", 0.0), ctx)
    else:
        # —— 原位移路径：root3d 整体 + offsets3d + 层级跟随 ——
        if root3d:
            for j in out:
                out[j][0] += rdx
                out[j][1] += rdy
                out[j][2] += rdz
        # 显式偏移（动作只需写“特殊骨骼”）
        explicit: dict[str, list[float]] = {}
        defined_axes: dict[str, set[int]] = {}
        for joint, comp in offsets.items():
            if joint in out:
                explicit[joint] = [_eval(comp.get("x", 0.0), ctx),
                                   _eval(comp.get("y", 0.0), ctx),
                                   _eval(comp.get("z", 0.0), ctx)]
                defined_axes[joint] = {k for k, ax in enumerate(("x", "y", "z")) if ax in comp}
        # 层级跟随（计算函数 resolve_follow3d）：
        # 节点局部位移 = 显式 offset + 从父节点继承（×链级传递系数 factor）。
        # 数据驱动：链父子关系来自 skeleton.json follow_chains，
        # 链级参数来自 skeleton.json follow_config（factor：0~1 衰减、1 完全跟随、>1 放大）。
        local = resolve_follow3d(explicit, defined_axes,
                                 skel3d.get("follow_chains") or {},
                                 skel3d.get("follow_config") or {})
        for j, d in local.items():
            if j in out:
                out[j][0] += d[0]
                out[j][1] += d[1]
                out[j][2] += d[2]
    # 3D IK：保持腿/臂骨长（pole 固定弯曲方向；弯曲余量 bend_factor 从物种约束数据读）
    bend_factor = float((skel3d.get("constraints") or {}).get("arm_bend_factor", 0.99))
    for chain in motion3d.get("ik3d", {}).get("chains", []):
        root, mid, tip = chain["root"], chain["mid"], chain["tip"]
        if root not in out or tip not in out:
            continue
        if chain.get("l1") is None or chain.get("l2") is None:
            l1 = math.dist(skel3d["joints"][root], skel3d["joints"][mid])
            l2 = math.dist(skel3d["joints"][mid], skel3d["joints"][tip])
        else:
            l1, l2 = chain["l1"], chain["l2"]
        out[mid], out[tip] = ik3d(out[root], out[tip], l1, l2,
                                  tuple(chain.get("pole", (0.0, 0.0, 1.0))),
                                  bend_factor)
    # 3D 刚性传播：仅位移版动作需要（脚掌/手掌板不撕裂）。
    # FK 分支已由关节旋转保证骨长与真实位置，刚性覆盖会破坏真实动捕数据 → 跳过。
    if not fk_mode:
        _propagate_rigid3d(out, skel3d["joints"], skel3d.get("rigid_chains", []))
    return out


def _propagate_rigid3d(out: dict, base: dict, rigid_chains: list[dict]) -> None:
    """3D 刚性传播：跟随关节 = 基准 + 驱动关节位移。

    rigid_chains 来自物种 constraints.rigid_chains（JSON 数据，不含硬编码关节名）。
    """
    for chain in rigid_chains:
        driver = chain["driver"]
        if driver not in out or driver not in base:
            continue
        delta = [out[driver][i] - base[driver][i] for i in range(3)]
        for f in chain.get("follow", []):
            if f in out and f in base:
                out[f] = [base[f][i] + delta[i] for i in range(3)]


def render_motion_3d(skel3d: dict, motion3d: dict, yaw_deg: float = 0.0,
                     pitch_deg: float = 0.0, distance: float = 600.0,
                     zoom: float = 1.0, pan_x: float = 0.0, pan_y: float = 0.0,
                     params: dict | None = None) -> Image.Image:
    """渲染 3D 动作的一帧（首帧），支持角度 + 距离 + 平移。"""
    pose = pose_3d(skel3d, motion3d, 0, params)
    return render_pose(pose, skel3d["bones"], yaw_deg, pitch_deg, distance, zoom,
                       center=tuple(skel3d.get("center", _CENTER)), pan_x=pan_x, pan_y=pan_y,
                       head_radius=float(skel3d.get("head_radius", 22.0)))


def _autofit_transform(joints2d: dict[str, tuple[float, float]],
                       zoom: float = 1.0, pan_x: float = 0.0, pan_y: float = 0.0,
                       margin: float = 0.12, max_scale: float = 8.0
                       ) -> tuple[float, float, float]:
    """根据投影点包围盒计算自动适配：填满画布并居中。

    以“填满画布 76% 面积”为基准缩放，再乘以用户 zoom（相对缩放），
    平移 = 居中偏移 + 用户 pan（相对平移）。这样默认预览大而清晰，
    相机控制里的 zoom/pan 仍按相对量生效。
    """
    xs = [p[0] for p in joints2d.values()]
    ys = [p[1] for p in joints2d.values()]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    w, h = maxx - minx, maxy - miny
    if w < 1 or h < 1:
        return zoom, pan_x, pan_y
    avail_w = _CANVAS_W * (1 - 2 * margin)
    avail_h = _CANVAS_H * (1 - 2 * margin)
    base = min(avail_w / w, avail_h / h)
    scale = min(max(base * zoom, 0.05), max_scale)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    tx = _CANVAS_W / 2 - cx * scale + pan_x
    ty = _CANVAS_H / 2 - cy * scale + pan_y
    return scale, tx, ty


def render_pose(pose: dict[str, list[float]], bones: list[list[str]],
                yaw_deg: float = 0.0, pitch_deg: float = 0.0,
                distance: float = 600.0, zoom: float = 1.0,
                center: tuple[float, float, float] | None = None,
                pan_x: float = 0.0, pan_y: float = 0.0,
                autofit: tuple[float, float, float] | None = None,
                head_radius: float = 22.0) -> Image.Image:
    """渲染任意 3D 姿势：角度（yaw/pitch）+ 距离（透视）+ 自动适配居中 + zoom/pan 相对量。

    ``autofit``：可传入固定的 (scale, tx, ty) 变换（如 GIF 各帧统一用首帧的适配，
    避免逐帧独立适配造成缩放抖动）。
    """
    from assetslab.render import BONE, JOINT, canvas, head, joint, bone

    image, draw = canvas()
    # 先以 zoom=1/pan=0 投影（distance 仅影响透视），再做自动适配（填满画布并居中）
    joints2d = project3d(pose, yaw_deg, pitch_deg, distance, 1.0, center=center,
                         pan_x=0.0, pan_y=0.0)
    if autofit is not None:
        scale, tx, ty = autofit
    else:
        scale, tx, ty = _autofit_transform(joints2d, zoom, pan_x, pan_y)
    joints2d = {k: (v[0] * scale + tx, v[1] * scale + ty) for k, v in joints2d.items()}
    # 头部椭圆：多首物种（三头飞龙）画出所有头（head / head_left / head_right），需在骨骼之上
    for hk in ("head", "head_left", "head_right"):
        if hk in joints2d:
            head(draw, joints2d[hk], BONE, radius=head_radius)
    for a, b in bones:
        if a in joints2d and b in joints2d:
            bone(draw, joints2d[a], joints2d[b], BONE)
    for pt in joints2d.values():
        joint(draw, pt)
    return image


def render_view(skel3d: dict, yaw_deg: float = 0.0, pitch_deg: float = 0.0,
                distance: float = 600.0, zoom: float = 1.0,
                pan_x: float = 0.0, pan_y: float = 0.0,
                width: int = 640, height: int = 480) -> Image.Image:
    """渲染 3D 骨架：角度（yaw/pitch）+ 距离（透视）+ 自动适配居中 + zoom/pan 相对量。"""
    from assetslab.render import BONE, JOINT, canvas, head, joint, bone

    image, draw = canvas()
    center = tuple(skel3d.get("center", _CENTER))
    joints2d = project3d(skel3d["joints"], yaw_deg, pitch_deg, distance, 1.0, center=center,
                         pan_x=0.0, pan_y=0.0)
    scale, tx, ty = _autofit_transform(joints2d, zoom, pan_x, pan_y)
    joints2d = {k: (v[0] * scale + tx, v[1] * scale + ty) for k, v in joints2d.items()}
    # 头部椭圆：多首物种（三头飞龙）画出所有头
    hr = float(skel3d.get("head_radius", 22.0))
    for hk in ("head", "head_left", "head_right"):
        if hk in joints2d:
            head(draw, joints2d[hk], BONE, radius=hr)
    for a, b in skel3d["bones"]:
        if a in joints2d and b in joints2d:
            bone(draw, joints2d[a], joints2d[b], BONE)
    for pt in joints2d.values():
        joint(draw, pt)
    return image


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> None:
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="3D 骨架投影预览（基于物种默认参数）")
    ap.add_argument("--species", default="human")
    ap.add_argument("--yaw", type=float, default=0.0, help="视角角（度）：0=front 90=side 180=back 45=斜")
    ap.add_argument("--out", default=None, help="输出 PNG 路径")
    args = ap.parse_args()

    skel3d = build_skeleton_3d(args.species)
    img = render_view(skel3d, args.yaw)
    if args.out:
        img.save(args.out)
        print(f"saved {args.out}")
    else:
        img.show()


if __name__ == "__main__":
    main()
