#!/usr/bin/env python3
"""数据驱动生成预设：只读 species/<id>/preset_schema.json（随物种自动派生）+ 解剖比例。

预设 schema（关节清单/参数/画布）来自 species/<id>/preset_schema.json（由 species 模块
随骨架自动生成/更新）；本脚本只补充“人设解剖比例表”（男女 × 儿童/成年/老年，模特身材），
为每个 3D 关节填充解剖学合理坐标，并自动从 3D 投影派生 2D 视图坐标。

用法:
  python scripts/generate_presets.py            # 生成全部预设
  python scripts/generate_presets.py model_female  # 只生成指定预设

生成的预设写入 assetslab/presets/<species>/<id>.json（positions_3d 为主，positions 为 2D 渲染派生层）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRESET_SCHEMA_JSON = ROOT / "assetslab" / "species" / "human" / "preset_schema.json"
PRESETS_DIR = ROOT / "assetslab" / "presets"

CX = 480.0  # 画布水平中线（坐标系原点）
FLOOR_Y = 470.0  # 地面线（脚底贴合）


# =========================================================================
# 2. 预设解剖比例表（模特身材，参考人体测量学）
# =========================================================================
# 每预设关键解剖参数：
#   title          显示名
#   gender         male / female
#   age            child / adult / elder
#   head_radius    头半径（决定头高 T = 2*head_radius）
#   shoulder       肩宽（两肩峰间距）
#   hip            髋宽（两大转子间距）
#   chest_depth    胸部前后凸（女性胸廓前突，z 正值）
#   waist_ratio    腰宽相对肩宽的收窄比（女性腰更细）
#   y: 各段长度（单位=头高 T）—— 躯干到髋 / 大腿 / 小腿 / 脚
#   slouch         老年驼背：上身前倾量（z 前移）
#   body           体型参数默认值（相对基准，人设特征）
PRESET_SPECS = {
    "model_male": {
        "title": "模特成年男性", "gender": "male", "age": "adult",
        "head_radius": 24.0, "shoulder": 96.0, "hip": 56.0, "chest_depth": 0.0, "waist_ratio": 0.78,
        "y": {"torso_hip": 3.4, "thigh": 1.7, "shin": 2.2, "foot": 0.6},
        "slouch": 0, "body": {},
    },
    "model_female": {
        "title": "模特成年女性", "gender": "female", "age": "adult",
        "head_radius": 23.0, "shoulder": 78.0, "hip": 72.0, "chest_depth": 8.0, "waist_ratio": 0.66,
        "y": {"torso_hip": 3.4, "thigh": 1.75, "shin": 2.25, "foot": 0.55},
        "slouch": 0, "body": {},
    },
    "boy_child": {
        "title": "男孩儿童", "gender": "male", "age": "child",
        "head_radius": 26.0, "shoulder": 56.0, "hip": 40.0, "chest_depth": 0.0, "waist_ratio": 0.85,
        "y": {"torso_hip": 3.2, "thigh": 1.3, "shin": 1.2, "foot": 0.3},
        "slouch": 0, "body": {"head_scale": 1.2},
    },
    "girl_child": {
        "title": "女孩儿童", "gender": "female", "age": "child",
        "head_radius": 25.0, "shoulder": 52.0, "hip": 44.0, "chest_depth": 2.0, "waist_ratio": 0.82,
        "y": {"torso_hip": 3.2, "thigh": 1.35, "shin": 1.2, "foot": 0.28},
        "slouch": 0, "body": {"head_scale": 1.2},
    },
    "male_elder": {
        "title": "老年男性", "gender": "male", "age": "elder",
        "head_radius": 23.0, "shoulder": 84.0, "hip": 62.0, "chest_depth": 0.0, "waist_ratio": 0.88,
        "y": {"torso_hip": 3.3, "thigh": 1.5, "shin": 1.9, "foot": 0.6},
        "slouch": 8, "body": {"shoulder_width": 0.9},
    },
    "female_elder": {
        "title": "老年女性", "gender": "female", "age": "elder",
        "head_radius": 22.0, "shoulder": 70.0, "hip": 74.0, "chest_depth": 6.0, "waist_ratio": 0.8,
        "y": {"torso_hip": 3.3, "thigh": 1.55, "shin": 1.9, "foot": 0.55},
        "slouch": 8, "body": {"shoulder_width": 0.92},
    },
}


# =========================================================================
# 3. 3D 关节坐标生成（解剖学 + 模特身材）
# =========================================================================
def _round(v: float) -> float:
    return round(v, 1)


def gen_joints3d(spec: dict) -> dict[str, list[float]]:
    """按解剖比例生成 39 个 3D 关节 [x(左右), y(上下), z(前后)]。

    默认 **T-pose（十字形）**：双臂水平打开、双腿并拢伸直、左右完全对称。
    修复历史问题：左右肢不再用 z = ±(深度) 制造“左前右后”的错位，
    而是让左右对称（同 z 深度）；手臂加长到解剖学比例（不再短小内弯）。
    """
    T = 2.0 * spec["head_radius"]          # 头高（单位）
    sw = spec["shoulder"]                   # 肩宽
    hw = spec["hip"]                        # 髋宽
    cd = spec["chest_depth"]                # 胸凸
    sl = spec["slouch"]                     # 驼背前倾
    y = spec["y"]
    height = y["torso_hip"] + y["thigh"] + y["shin"] + y["foot"]  # 总高（头）
    top_y = FLOOR_Y - height * T            # 头顶 y（脚底对齐 floor）

    def Y(ratio: float) -> float:
        return top_y + ratio * T            # ratio 为距头顶的头数

    # 躯干中线 y（距头顶头数）
    mid = {
        "head": 0.5, "jaw": 1.0, "neck": 1.3, "upper_chest": 1.6,
        "chest": 2.0, "sternum": 2.35, "waist": 2.6, "abdomen": 2.9,
        "pelvis": 3.2,
    }
    # 髋/腿 y
    hip_y = y["torso_hip"]
    knee_y = hip_y + y["thigh"]
    ankle_y = knee_y + y["shin"]
    foot_y = ankle_y + y["foot"]

    # 肩/臂（头数）：上臂 ~1.3、前臂 ~1.15、手 ~0.15 —— 手臂够长，手可达大腿
    shoulder_y = 1.55
    upper_arm = 1.3
    forearm = 1.15
    hand = 0.15

    # 左右对称助手（x 用距中线偏移）
    def lr(side: str, off: float) -> float:
        return CX - off if side == "left" else CX + off

    sh_half = sw / 2.0
    hp_half = hw / 2.0
    J: dict[str, list[float]] = {}

    # --- 中线（z=0 基准；胸/颈带前凸 cd、驼背 sl） ---
    for name, r in mid.items():
        z = 0.0
        if name in ("neck", "upper_chest", "chest", "sternum"):
            z += cd * 0.6 if name in ("chest", "sternum") else cd * 0.2
        z += sl * 0.7 if name in ("head", "jaw", "neck") else (sl * 0.4 if name in ("upper_chest", "chest", "sternum") else 0)
        J[name] = [CX, _round(Y(r)), _round(z)]

    # --- T-pose 手臂：水平打开（同肩高 y），左右 z 对称（自然前倾一档） ---
    arm_z = 8.0 + cd * 0.2 + sl * 0.1
    for side in ("left", "right"):
        sign = 1 if side == "left" else -1
        shx = CX - sh_half * sign
        J[f"clavicle_{side}"] = [CX - sh_half * 0.5 * sign, _round(Y(1.5)), _round(4.0 + cd * 0.2)]
        J[f"shoulder_{side}"] = [shx, _round(Y(shoulder_y)), _round(arm_z)]
        J[f"elbow_{side}"] = [CX - (sh_half + upper_arm * T) * sign, _round(Y(shoulder_y)), _round(arm_z)]
        J[f"wrist_{side}"] = [CX - (sh_half + (upper_arm + forearm) * T) * sign, _round(Y(shoulder_y)), _round(arm_z)]
        J[f"palm_{side}"] = [CX - (sh_half + (upper_arm + forearm + hand) * T) * sign, _round(Y(shoulder_y)), _round(arm_z)]
        J[f"finger_{side}"] = [CX - (sh_half + (upper_arm + forearm + hand + 0.08) * T) * sign, _round(Y(shoulder_y)), _round(arm_z)]

    # --- 肋骨（左右对称） ---
    for side in ("left", "right"):
        sign = 1 if side == "left" else -1
        J[f"rib_upper_{side}"] = [CX - sh_half * 0.42 * sign, _round(Y(2.0)), _round(4.0 + cd * 0.2)]
        J[f"rib_lower_{side}"] = [CX - sh_half * 0.38 * sign, _round(Y(2.3)), _round(4.0 + cd * 0.2)]

    # --- 骨盆 / 髋 / 腿：伸直、双脚并拢（踝/脚靠中，左右 z 对称） ---
    leg_z = 4.0
    for side in ("left", "right"):
        sign = 1 if side == "left" else -1
        J[f"iliac_{side}"] = [CX - hp_half * 0.7 * sign, _round(Y(hip_y + 0.12)), _round(leg_z)]
        J[f"hip_{side}"] = [CX - hp_half * sign, _round(Y(hip_y + 0.15)), _round(leg_z)]
        J[f"knee_{side}"] = [CX - hp_half * 0.85 * sign, _round(Y(knee_y)), _round(leg_z)]
        J[f"ankle_{side}"] = [CX - 2.0 * sign, _round(Y(ankle_y)), _round(leg_z)]
        J[f"heel_{side}"] = [CX - 2.0 * sign, _round(Y(ankle_y + 0.35)), _round(leg_z)]
        J[f"foot_{side}"] = [CX - 2.0 * sign, _round(Y(foot_y)), _round(leg_z)]
        J[f"toe_{side}"] = [CX - 6.0 * sign, _round(Y(foot_y)), _round(leg_z + 4.0)]

    return J


# =========================================================================
# 4. 2D 视图坐标派生（front/side/back 从 3D 投影，供 2D 兼容渲染层）
# =========================================================================
def _side_name_map() -> dict[str, str]:
    return {
        "head": "head", "jaw": "jaw", "neck": "neck", "upper_chest": "upper_chest",
        "chest": "chest", "sternum": "sternum", "waist": "waist", "abdomen": "abdomen",
        "pelvis": "pelvis",
        "clavicle_right": "clavicle_front", "clavicle_left": "clavicle_rear",
        "shoulder_right": "front_shoulder", "shoulder_left": "rear_shoulder",
        "elbow_right": "front_elbow", "elbow_left": "rear_elbow",
        "wrist_right": "front_wrist", "wrist_left": "rear_wrist",
        "palm_right": "front_palm", "palm_left": "rear_palm",
        "finger_right": "front_finger", "finger_left": "rear_finger",
        "rib_upper_right": "rib_front", "rib_upper_left": "rib_rear",
        "hip_right": "front_hip", "hip_left": "rear_hip",
        "knee_right": "front_knee", "knee_left": "rear_knee",
        "ankle_right": "front_ankle", "ankle_left": "rear_ankle",
        "heel_right": "front_heel", "heel_left": "rear_heel",
        "foot_right": "front_foot", "foot_left": "rear_foot",
        "toe_right": "front_toe", "toe_left": "rear_toe",
    }


def _back_name_map() -> dict[str, str]:
    m = {
        "head": "head", "jaw": "jaw", "neck": "neck", "upper_chest": "upper_chest",
        "chest": "chest", "sternum": "sternum", "waist": "waist", "abdomen": "abdomen",
        "pelvis": "pelvis",
        "clavicle_left": "clavicle_left", "clavicle_right": "clavicle_right",
        "rib_upper_left": "rib_upper_left", "rib_upper_right": "rib_upper_right",
        "rib_lower_left": "rib_lower_left", "rib_lower_right": "rib_lower_right",
    }
    for part, lp, rp in (
        ("shoulder", "rear_shoulder_left", "rear_shoulder_right"),
        ("elbow", "rear_elbow_left", "rear_elbow_right"),
        ("wrist", "rear_wrist_left", "rear_wrist_right"),
        ("palm", "rear_palm_left", "rear_palm_right"),
        ("finger", "rear_finger_left", "rear_finger_right"),
        ("hip", "rear_hip_left", "rear_hip_right"),
        ("knee", "rear_knee_left", "rear_knee_right"),
        ("ankle", "rear_ankle_left", "rear_ankle_right"),
        ("heel", "rear_heel_left", "rear_heel_right"),
        ("foot", "rear_foot_left", "rear_foot_right"),
        ("toe", "rear_toe_left", "rear_toe_right"),
    ):
        # 背面观察：观察者左侧 = 人体右侧 → 名互相对调
        m[f"{part}_right"] = lp
        m[f"{part}_left"] = rp
    return m


def derive_views_2d(j3: dict[str, list[float]]) -> dict[str, dict[str, list[float]]]:
    """从 3D 坐标派生 front/side/back 2D 坐标（front/side/back 为引擎渲染兼容层）。"""
    front, side, back = {}, {}, {}
    smap, bmap = _side_name_map(), _back_name_map()

    for name, (x, y, z) in j3.items():
        front[name] = [x, y]                      # 前视：x 左右 / y 上下
    for name, (x, y, z) in j3.items():
        if name in smap:
            side[smap[name]] = [-z, y]            # 侧视：x 前后(深度) / y 上下；近侧(right, z-)在画面右
    for name, (x, y, z) in j3.items():
        if name in bmap:
            back[bmap[name]] = [2 * CX - x, y]    # 后视：左右镜像
    return {"front": front, "side": side, "back": back}


# =========================================================================
# 5. 读取物种预设 schema（由 species 模块随骨架自动派生）
# =========================================================================
def load_schema() -> dict:
    """读 species/<id>/preset_schema.json。"""
    if not PRESET_SCHEMA_JSON.is_file():
        raise SystemExit(f"preset_schema not found: {PRESET_SCHEMA_JSON}（先创建/更新物种以派生 schema）")
    return json.loads(PRESET_SCHEMA_JSON.read_text(encoding="utf-8"))


def build_preset(spec: dict, schema: dict) -> dict:
    j3 = gen_joints3d(spec)
    views = derive_views_2d(j3)
    params = schema.get("params", {})
    body = dict(schema.get("body_default", {}))
    body.update(spec.get("body", {}))
    # 只保留 schema 定义的参数（防止混入非骨架参数）
    body = {k: v for k, v in body.items() if k in params}
    canvas = dict(schema.get("canvas", {"width": 960, "height": 600, "floor_y": FLOOR_Y}))
    return {
        "preset_id": None,  # 由调用方填充
        "schema": "assetslab_preset_v3",
        "species": schema.get("species") or "human",
        "head_radius": spec.get("head_radius", schema.get("head_radius", 24)),
        "canvas": canvas,
        "params": params,
        "body": body,
        "positions": views,
        "positions_3d": j3,
    }


def main() -> None:
    targets = sys.argv[1:] or list(PRESET_SPECS.keys())
    schema = load_schema()
    print(f"preset_schema: {len(schema.get('joints_3d', []))} joints_3d, "
          f"{len(schema.get('params', {}))} params, "
          f"views_2d { {k: len(v) for k, v in schema.get('views_2d', {}).items()} }")
    species_dir = PRESETS_DIR / (schema.get("species") or "human")
    species_dir.mkdir(parents=True, exist_ok=True)
    for pid in targets:
        if pid not in PRESET_SPECS:
            print(f"unknown preset: {pid} (available: {list(PRESET_SPECS)})")
            continue
        spec = PRESET_SPECS[pid]
        data = build_preset(spec, schema)
        data["preset_id"] = pid
        data["title"] = spec["title"]
        data["description"] = (f"{spec['gender']} · {spec['age']}，模特身材（解剖学比例）。"
                               f"头径 {2*spec['head_radius']:.0f}px，肩宽 {spec['shoulder']:.0f}px，髋宽 {spec['hip']:.0f}px。")
        path = species_dir / f"{pid}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"generated {path.name} -> {species_dir.name}/: joints3d={len(data['positions_3d'])}, views={ {k: len(v) for k, v in data['positions'].items()} }")


if __name__ == "__main__":
    main()
