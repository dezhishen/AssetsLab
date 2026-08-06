#!/usr/bin/env python3
"""AssetsLab — 3D 动作验证（阶段 2，walk3d 试点）。

按"JSON 定义、参数化渲染"准则，对 3D 动作（offsets3d + ik3d）做客观约束检查：
  bone   骨长保持（IK 后腿/臂长 vs 静态基准）
  ground 支撑脚贴地（3D 全局 y，floor=470）
  smooth 帧间位移平滑（无突变）
  sym    左右半周期镜像（3D 空间）
  param  参数拉满有效（有变化、不撕裂）

用法：
  python scripts/verify_motions3d.py
  python scripts/verify_motions3d.py --preset female
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from assetslab.skeleton3d import build_skeleton_3d, pose_3d

FLOOR_Y = 470.0


def sample3d(preset_id: str, motion3d: dict, params: dict | None = None,
             frame_count: int | None = None) -> list[dict[str, list[float]]]:
    """采样 3D 动作全部帧的姿势（3D 坐标）。"""
    skel3d = build_skeleton_3d(preset_id, motion3d.get("species", "human"))
    n = frame_count or int(motion3d.get("frame_count", 8))
    return [pose_3d(skel3d, motion3d, i, params) for i in range(n)]


def _leg_chains(motion3d: dict) -> list[tuple[str, str, str]]:
    legs = []
    for c in motion3d.get("ik3d", {}).get("chains", []):
        if "hip" in c["root"]:
            legs.append((c["root"], c["mid"], c["tip"]))
    return legs


def verify(preset_id: str, motion3d: dict, params: dict | None = None) -> list[dict]:
    """返回 violations 列表（空 = 全 PASS）。"""
    from assetslab.skeleton3d import load_species
    v: list[dict] = []
    sp = load_species(motion3d.get("species", "human"))
    skel3d = build_skeleton_3d(preset_id, motion3d.get("species", "human"))
    n = int(motion3d.get("frame_count", 8))
    frames = [pose_3d(skel3d, motion3d, i, params) for i in range(n)]

    # 刚性跟随关节（脚掌/手掌）与脚部着地检查集合：从骨架 rigid_chains 读（数据驱动）
    rigid_follow: set[str] = set()
    feet_set: list[str] = []
    for c in sp.get("constraints", {}).get("rigid_chains", {}).get("chains", []):
        rigid_follow.update(c.get("follow", []))
        if "ankle" in c["driver"]:  # 踝链的跟随里含 foot
            feet_set = [f for f in c.get("follow", []) if f.endswith("foot")]

    # ---- 1. 骨长保持（IK 腿/臂）----
    for chain in motion3d.get("ik3d", {}).get("chains", []):
        r, m, t = chain["root"], chain["mid"], chain["tip"]
        l1 = math.dist(skel3d["joints"][r], skel3d["joints"][m])
        l2 = math.dist(skel3d["joints"][m], skel3d["joints"][t])
        for i in range(n):
            a = math.dist(frames[i][r], frames[i][m])
            b = math.dist(frames[i][m], frames[i][t])
            for name, got, base in (("l1", a, l1), ("l2", b, l2)):
                if abs(got - base) > 0.05 * base:
                    v.append({"constraint": "bone", "detail": f"f{i} {m} {name}: {got:.1f} vs {base:.1f}"})
                    break

    # ---- 2. 支撑脚贴地（每帧至少一脚 y ≥ floor - tol；feet 从骨架刚性链读）----
    tol = 12.0
    for i in range(n):
        ys = [frames[i][f][1] for f in feet_set if f in frames[i]]
        if ys and all(y < FLOOR_Y - tol for y in ys):
            v.append({"constraint": "ground", "detail": f"f{i}: 双脚离地 (y={[round(y) for y in ys]})"})

    # ---- 3. 平滑（帧间位移，排除刚性跟随关节）----
    joints = [j for j in frames[0] if j not in rigid_follow]
    for j in joints:
        speeds = [math.dist(frames[i][j], frames[(i + 1) % n][j]) for i in range(n)]
        avg = sum(speeds) / n
        if avg > 0.01 and max(speeds) > max(avg * 3.0, 30):
            v.append({"constraint": "smooth", "detail": f"{j}: 帧间速度突变 max={max(speeds):.1f} avg={avg:.1f}"})

    # ---- 4. 左右对称（数据驱动：读骨架 symmetry3d；自适应对齐）----
    # 交替步态（walk/run）：半周期镜像（左腿 f[i] vs 右腿 f[i+half]）；
    # 同步动作（jump/idle）：同帧比较（左腿 f[i] vs 右腿 f[i]）。
    # 取两种对齐中更对称者，自动适配动作相位结构，不硬编码动作类型。
    sp_sym = sp.get("constraints", {}).get("symmetry3d", {})
    sym_pairs = sp_sym.get("pairs", [])
    s_tol = sp_sym.get("tolerance", 8.0)
    half = n // 2
    for lj, rj in sym_pairs:
        if lj not in frames[0] or rj not in frames[0]:
            continue
        bl = skel3d["joints"][lj]
        br = skel3d["joints"][rj]
        err_half = 0.0
        err_same = 0.0
        for i in range(n):
            dl = [frames[i][lj][k] - bl[k] for k in range(3)]
            dr_half = [frames[(i + half) % n][rj][k] - br[k] for k in range(3)]
            dr_same = [frames[i][rj][k] - br[k] for k in range(3)]
            err_half += abs(dl[0]-dr_half[0]) + abs(dl[1]-dr_half[1]) + abs(dl[2]-dr_half[2])
            err_same += abs(dl[0]-dr_same[0]) + abs(dl[1]-dr_same[1]) + abs(dl[2]-dr_same[2])
        err = min(err_half, err_same) / n
        if err > s_tol:
            v.append({"constraint": "sym", "detail": f"{lj}/{rj}: 不对称 {err:.1f}"})

    # ---- 5. 顺拐检查（数据驱动：读 species constraints.coordination 的同侧对，
    #          从动作 JSON 的 offsets3d 信号相位判断摆动反相，不依赖渲染/root）----
    from assetslab.motion import _build_signals, _resolve_params

    coord = sp.get("constraints", {}).get("coordination", {})
    if coord:
        axis = coord.get("axis", "z")
        sigfns = _build_signals(motion3d)
        pctx = {"params": _resolve_params(motion3d, params), "frame_count": n, "signals": sigfns}

        def _off_signal(expr):
            if isinstance(expr, dict):
                if "signal" in expr:
                    return expr["signal"]
                for v in expr.values():
                    r = _off_signal(v)
                    if r:
                        return r
            return None

        offsets = motion3d.get("offsets3d", {})
        for leg_j, arm_j in coord.get("pairs", []):
            leg_sig = _off_signal(offsets.get(leg_j, {}).get(axis))
            arm_sig = _off_signal(offsets.get(arm_j, {}).get(axis))
            if not leg_sig or not arm_sig:
                continue
            leg_vals = [sigfns[leg_sig]({**pctx, "phase": math.tau*i/n, "index": i}) for i in range(n)]
            arm_vals = [sigfns[arm_sig]({**pctx, "phase": math.tau*i/n, "index": i}) for i in range(n)]
            err = sum(min(abs(l), abs(a)) for l, a in zip(leg_vals, arm_vals) if l*a > 0)
            if err > 6.0:
                v.append({"constraint": "coord", "detail": f"顺拐 {leg_j}/{arm_j}（{axis} 轴同相，err={err:.1f}）"})

    # ---- 6. 参数有效（intensity 拉满 vs 默认差异；用动作 JSON 的第一个偏移关节测量）----
    default = [pose_3d(skel3d, motion3d, i, None) for i in range(n)]
    full = [pose_3d(skel3d, motion3d, i, {"intensity": 1.5}) for i in range(n)]
    test_joint = next(iter(motion3d.get("offsets3d", {})), None)
    if test_joint and test_joint in default[0]:
        diff = sum(math.dist(default[i][test_joint], full[i][test_joint]) for i in range(n))
        if diff < 1.0:
            v.append({"constraint": "param", "detail": f"intensity 无效（无变化）"})

    return v


def main() -> None:
    ap = argparse.ArgumentParser(description="3D 动作验证")
    ap.add_argument("--preset", default="standard")
    ap.add_argument("--action", default="all", help="动作 id；默认 all 扫描该物种所有 3D 动作")
    ap.add_argument("--species", default="human")
    args = ap.parse_args()

    actions_dir = ROOT / "assetslab" / "species" / args.species / "actions3d"
    if args.action == "all":
        action_ids = sorted(p.stem for p in actions_dir.glob("*.json"))
    else:
        action_ids = [args.action]

    labels = ["bone", "ground", "smooth", "sym", "coord", "param"]
    print(f"3D 动作验证: {args.species} @ {args.preset}")
    print(f"  {'motion':8s} " + "  ".join(f"{c:6s}" for c in labels))
    all_ok = True
    for aid in action_ids:
        path = actions_dir / f"{aid}.json"
        motion3d = json.load(open(path))
        v = verify(args.preset, motion3d)
        by_type = {c: [x for x in v if x["constraint"] == c] for c in labels}
        row = f"  {aid:8s} " + "  ".join(
            f"{c:6s}:{'PASS' if not by_type[c] else f'FAIL({len(by_type[c])})'}"
            for c in labels
        )
        print(row)
        if v:
            all_ok = False
            for x in v[:10]:
                print(f"    · {x['constraint']}: {x['detail']}")
    print("  " + ("ALL CHECKS PASS" if all_ok else "FAILURES FOUND"))


if __name__ == "__main__":
    main()
