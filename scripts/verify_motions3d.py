#!/usr/bin/env python3
"""AssetsLab — 3D 动作验证（数据驱动）。

所有阈值 / 关节 / 模式均从物种 skeleton.json 的 constraints 定义读取，
不写死任何数值或关节名；动作的贴地模式按 motion_id 前缀从 ground_contact 推导。
检查项（每项对应 constraints 里的一个数据定义）：
  bone    骨长保持（IK 后腿/臂长 vs 静态基准）—— bone_length.tolerance
  ground  支撑脚贴地（walk/run/idle/jump 各自 mode）—— ground_contact
  smooth  帧间位移平滑（无突变）—— smoothness.max_frame_disp
  sym     左右对称（3D 半周期镜像）—— symmetry3d + symmetry.skip_motions
  joint   膝/肘弯曲方向（front/side 视图）—— joint_direction
  elbow   肘关节张开角度 —— elbow_articulation
  coord   对侧协调（顺拐）—— coordination
  param   参数有效（intensity 拉满有变化）—— 动作 params + param_effect

用法：
  python scripts/verify_motions3d.py
  python scripts/verify_motions3d.py --action all
  python scripts/verify_motions3d.py --species three_head_dragon --action all
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from assetslab.skeleton3d import build_skeleton_3d, pose_3d, load_species
from assetslab.config import DEFAULT_DATA_DIR

# 引擎通用默认（仅当物种数据未定义该约束时兜底；数据定义优先）
DEFAULT_BONE_TOL = 0.05
DEFAULT_MAX_DISP = 60.0
DEFAULT_SYM_TOL = 8.0
DEFAULT_COORD_TOL = 6.0
DEFAULT_PARAM_MIN_DIFF = 1.0


def _view_to_3d(name: str, view: str, joints: dict) -> str | None:
    """把视图关节名（front/side/back）映射回 3D 关节名（数据驱动命名规则）。"""
    if view == 'front':
        return name if name in joints else None
    if view == 'side':
        if name.startswith('front_') and (name[6:] + '_left') in joints:
            return name[6:] + '_left'
        if name.startswith('rear_') and (name[5:] + '_right') in joints:
            return name[5:] + '_right'
        return name if name in joints else None
    if view == 'back':
        n = name[5:] if name.startswith('rear_') else name
        return n if n in joints else None
    return name if name in joints else None


def _planar(pose: dict, joint: str, view: str) -> tuple[float, float]:
    """取关节在指定视图平面上的屏幕坐标：front→(x,y)、side→(z,y)、back→(-x,y)。"""
    x, y, z = pose[joint]
    if view == 'side':
        return z, y
    if view == 'back':
        return -x, y
    return x, y


def _cross(pose: dict, root: str, mid: str, tip: str, view: str) -> float:
    ax, ay = _planar(pose, root, view)
    bx, by = _planar(pose, mid, view)
    cx, cy = _planar(pose, tip, view)
    ux, uy = cx - ax, cy - ay
    vx, vy = bx - ax, by - ay
    return ux * vy - uy * vx


def _ground_mode(motion3d: dict, gc: dict) -> dict | None:
    """从动作定义推导贴地模式：动作显式声明优先，否则按 motion_id 前缀匹配 ground_contact。"""
    if isinstance(motion3d.get('ground'), dict):
        return motion3d['ground']
    mid = motion3d.get('motion_id', '')
    for key, cfg in gc.items():
        if isinstance(cfg, dict) and isinstance(cfg.get('mode'), str) and mid.startswith(key):
            return cfg
    return None


def verify(species_id: str, motion3d: dict, params: dict | None = None,
           species_root: Path | None = None) -> list[dict]:
    """返回 violations 列表（空 = 全 PASS）。species_root 覆盖物种数据目录（默认 data/）。"""
    v: list[dict] = []
    sp = load_species(species_id, species_root)
    skel3d = build_skeleton_3d(species_id, species_root=species_root)
    n = int(motion3d.get('frame_count', 8))
    frames = [pose_3d(skel3d, motion3d, i, params) for i in range(n)]
    base = skel3d['joints']
    joints = set(base)
    mid_id = motion3d.get('motion_id', '')
    cons = sp.get('constraints', {}) or {}

    # 刚性跟随关节（脚掌/手掌）：从骨架 rigid_chains 读
    rigid_follow: set[str] = set()
    for c in cons.get('rigid_chains', {}).get('chains', []):
        rigid_follow.update(c.get('follow', []))

    # ---- 1. 骨长保持（IK 链；容差从 bone_length 读）----
    bone_tol = float(cons.get('bone_length', {}).get('tolerance', DEFAULT_BONE_TOL))
    for chain in motion3d.get('ik3d', {}).get('chains', []):
        r, m, t = chain['root'], chain['mid'], chain['tip']
        l1 = math.dist(base.get(r, []), base.get(m, []))
        l2 = math.dist(base.get(m, []), base.get(t, []))
        for i in range(n):
            a = math.dist(frames[i].get(r, base.get(r, [])), frames[i].get(m, base.get(m, [])))
            b = math.dist(frames[i].get(m, base.get(m, [])), frames[i].get(t, base.get(t, [])))
            for name, got, bl in (('l1', a, l1), ('l2', b, l2)):
                if bl > 1e-6 and abs(got - bl) > bone_tol * bl:
                    v.append({'constraint': 'bone', 'detail': f'f{i} {m} {name}: {got:.1f} vs {bl:.1f}'})
                    break

    # ---- 2. 支撑脚贴地（ground_contact 定义：floor/feet/mode；未定义脚则不检查）----
    gc = cons.get('ground_contact', {})
    feet = list(gc.get('feet', {}).get('front', []))
    if gc and feet:
        floor_y = float(gc.get('floor_y', 470.0))
        gm = _ground_mode(motion3d, gc)
        if gm is None and motion3d.get('flight'):
            mode = 'flight_allowed'
        elif gm is None:
            mode = 'one_planted'
            tol = 12.0
        else:
            mode = gm.get('mode', 'one_planted')
            tol = float(gm.get('tol', 12.0))
            max_flight = int(gm.get('max_flight', 2))
        if mode == 'all_planted':
            for i in range(n):
                ys = [frames[i][f][1] for f in feet if f in frames[i]]
                if ys and any(y < floor_y - tol for y in ys):
                    v.append({'constraint': 'ground', 'detail': f'f{i}: 有脚离地 y={[round(y) for y in ys]}'})
        elif mode == 'one_planted':
            for i in range(n):
                ys = [frames[i][f][1] for f in feet if f in frames[i]]
                if ys and all(y < floor_y - tol for y in ys):
                    v.append({'constraint': 'ground', 'detail': f'f{i}: 双脚离地 y={[round(y) for y in ys]}'})
        elif mode == 'flight_limited':
            off = sum(1 for i in range(n)
                      if [frames[i][f][1] for f in feet if f in frames[i]]
                      and all(y < floor_y - tol for y in [frames[i][f][1] for f in feet if f in frames[i]]))
            if off > max_flight:
                v.append({'constraint': 'ground', 'detail': f'flight_limited: 双脚离地 {off} 帧 > {max_flight}'})

    # ---- 3. 帧间平滑（smoothness.max_frame_disp）----
    max_disp = float(cons.get('smoothness', {}).get('max_frame_disp', DEFAULT_MAX_DISP))
    for j in frames[0]:
        if j in rigid_follow:
            continue
        speeds = [math.dist(frames[i][j], frames[(i + 1) % n][j]) for i in range(n)]
        avg = sum(speeds) / n
        if avg > 0.01 and max(speeds) > max(avg * 3.0, max_disp):
            v.append({'constraint': 'smooth', 'detail': f'{j}: 帧间速度突变 max={max(speeds):.1f} avg={avg:.1f}'})

    # ---- 4. 左右对称（symmetry3d + symmetry.skip_motions）----
    sym2 = cons.get('symmetry', {})
    skip = sym2.get('skip_motions', [])
    sym3 = cons.get('symmetry3d', {})
    if not any(mid_id.startswith(s) for s in skip) and sym3:
        pairs = sym3.get('pairs', [])
        s_tol = float(sym3.get('tolerance', DEFAULT_SYM_TOL))
        half = n // 2
        for lj, rj in pairs:
            if lj not in frames[0] or rj not in frames[0]:
                continue
            bl, br = base[lj], base[rj]
            err_half = err_same = 0.0
            for i in range(n):
                dl = [frames[i][lj][k] - bl[k] for k in range(3)]
                dh = [frames[(i + half) % n][rj][k] - br[k] for k in range(3)]
                ds = [frames[i][rj][k] - br[k] for k in range(3)]
                err_half += abs(dl[0] + dh[0]) + abs(dl[1] - dh[1]) + abs(dl[2] - dh[2])
                err_same += abs(dl[0] + ds[0]) + abs(dl[1] - ds[1]) + abs(dl[2] - ds[2])
            err = min(err_half, err_same) / n
            if err > s_tol:
                v.append({'constraint': 'sym', 'detail': f'{lj}/{rj}: 不对称 {err:.1f}'})

    # ---- 5. 膝/肘弯曲方向（joint_direction；按数据 bend 语义直接判定，不依赖基准符号）----
    for it in cons.get('joint_direction', []):
        if any(mid_id.startswith(s) for s in it.get('skip_motions', [])):
            continue
        view = it.get('view', 'front')
        r3 = _view_to_3d(it['root'], view, joints)
        m3 = _view_to_3d(it['mid'], view, joints)
        t3 = _view_to_3d(it['tip'], view, joints)
        if not (r3 and m3 and t3):
            continue
        bend = it.get('bend')
        tol = float(it.get('tol', 3.0))

        def _line_at_mid(pose, axis):
            """root→tip 连线在 mid 高度(y)处 axis 轴上的插值。"""
            r, m, t = pose[r3], pose[m3], pose[t3]
            if abs(t[1] - r[1]) < 1e-6:
                return None
            frac = (m[1] - r[1]) / (t[1] - r[1])
            return r[axis] + (t[axis] - r[axis]) * frac

        bad = 0
        for i in range(n):
            p = frames[i]
            ok = True
            if view == 'side':
                lz = _line_at_mid(p, 2)
                if lz is None:
                    continue
                if bend == 'forward':
                    ok = p[m3][2] > lz + tol
                elif bend == 'backward':
                    ok = p[m3][2] < lz - tol
            else:  # front：outward/inward（左肢向 -x 外，右肢向 +x 外）
                lx = _line_at_mid(p, 0)
                if lx is None:
                    continue
                outward_neg = r3.endswith('_left')
                if bend == 'outward':
                    # 肘不得明显向内反折；中立/向外均可
                    ok = (p[m3][0] <= lx + tol) if outward_neg else (p[m3][0] >= lx - tol)
                elif bend == 'inward':
                    ok = (p[m3][0] > lx + tol) if outward_neg else (p[m3][0] < lx - tol)
            if not ok:
                bad += 1
        if bad > n // 4:
            v.append({'constraint': 'joint', 'detail': f'{it.get("id")}: {bad}/{n} 帧弯曲方向不符（bend={bend}）'})

    # ---- 6. 肘关节张开角度（elbow_articulation）----
    eb = cons.get('elbow_articulation', {})
    if eb and not any(mid_id.startswith(s) for s in eb.get('skip_motions', [])):
        min_deg = float(eb.get('min_spread_deg', 6.0))
        for view, chains in eb.get('chains', {}).items():
            for (e, w, pp) in chains:
                e3 = _view_to_3d(e, view, joints)
                w3 = _view_to_3d(w, view, joints)
                p3 = _view_to_3d(pp, view, joints)
                if not (e3 and w3 and p3):
                    continue
                for i in range(n):
                    ew = [frames[i][w3][k] - frames[i][e3][k] for k in range(3)]
                    wp = [frames[i][p3][k] - frames[i][w3][k] for k in range(3)]
                    el = math.dist(frames[i][e3], frames[i][w3])
                    wl = math.dist(frames[i][w3], frames[i][p3])
                    if el < 1e-6 or wl < 1e-6:
                        continue
                    deg = math.degrees(math.acos(max(-1.0, min(1.0, sum(ew[k] * wp[k] for k in range(3)) / (el * wl)))))
                    if deg < min_deg:
                        v.append({'constraint': 'elbow', 'detail': f'f{i} {e3}: 肘张角 {deg:.1f}° < {min_deg}°'})
                        break

    # ---- 7. 顺拐（coordination；tol 从数据读）----
    coord = cons.get('coordination', {})
    if coord:
        from assetslab.motion import _build_signals, _resolve_params
        axis = coord.get('axis', 'z')
        c_tol = float(coord.get('tol', DEFAULT_COORD_TOL))
        sigfns = _build_signals(motion3d)
        pctx = {'params': _resolve_params(motion3d, params), 'frame_count': n, 'signals': sigfns}

        def _off_signal(expr):
            if isinstance(expr, dict):
                if 'signal' in expr:
                    return expr['signal']
                for vv in expr.values():
                    r = _off_signal(vv)
                    if r:
                        return r
            return None

        offsets = motion3d.get('offsets3d', {})
        for leg_j, arm_j in coord.get('pairs', []):
            leg_sig = _off_signal(offsets.get(leg_j, {}).get(axis))
            arm_sig = _off_signal(offsets.get(arm_j, {}).get(axis))
            if not leg_sig or not arm_sig:
                continue
            leg_vals = [sigfns[leg_sig]({**pctx, 'phase': math.tau * i / n, 'index': i}) for i in range(n)]
            arm_vals = [sigfns[arm_sig]({**pctx, 'phase': math.tau * i / n, 'index': i}) for i in range(n)]
            err = sum(min(abs(l), abs(a)) for l, a in zip(leg_vals, arm_vals) if l * a > 0)
            if err > c_tol:
                v.append({'constraint': 'coord', 'detail': f'顺拐 {leg_j}/{arm_j}（{axis} 同相 err={err:.1f}）'})

    # ---- 8. 参数有效（intensity 拉满 vs 默认；强度取动作定义 max）----
    inten = motion3d.get('params', {}).get('intensity', {})
    max_inten = float(inten.get('max', 1.5))
    min_diff = float(cons.get('param_effect', {}).get('min_diff', DEFAULT_PARAM_MIN_DIFF))
    if inten:
        default = [pose_3d(skel3d, motion3d, i, None) for i in range(n)]
        full = [pose_3d(skel3d, motion3d, i, {'intensity': max_inten}) for i in range(n)]
        test_joint = next(iter(motion3d.get('offsets3d', {})), None)
        if test_joint and test_joint in default[0]:
            diff = sum(math.dist(default[i][test_joint], full[i][test_joint]) for i in range(n))
            if diff < min_diff:
                v.append({'constraint': 'param', 'detail': f'intensity 无效（变化 {diff:.2f} < {min_diff}）'})
    return v


def main() -> None:
    ap = argparse.ArgumentParser(description='3D 动作验证（数据驱动，基于物种默认参数）')
    ap.add_argument('--action', default='all', help='动作 id；默认 all 扫描该物种所有 3D 动作')
    ap.add_argument('--species', default='human')
    ap.add_argument('--data-dir', default=None,
                    help='数据目录（默认仓库根 data/，测试用 test-data/）')
    args = ap.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else DEFAULT_DATA_DIR
    species_root = data_dir / 'species'
    actions_dir = species_root / args.species / 'actions3d'
    if args.action == 'all':
        action_ids = sorted(p.stem for p in actions_dir.glob('*.json'))
    else:
        action_ids = [args.action]

    labels = ['bone', 'ground', 'smooth', 'sym', 'joint', 'elbow', 'coord', 'param']
    print(f'3D 动作验证: {args.species}')
    print(f'  {"motion":8s} ' + '  '.join(f'{c:6s}' for c in labels))
    all_ok = True
    for aid in action_ids:
        path = actions_dir / f'{aid}.json'
        motion3d = json.load(open(path))
        v = verify(args.species, motion3d, species_root=species_root)
        by_type = {c: [x for x in v if x['constraint'] == c] for c in labels}
        row = f'  {aid:8s} ' + '  '.join(
            f'{c:6s}:{"PASS" if not by_type[c] else f"FAIL({len(by_type[c])})"}'
            for c in labels)
        print(row)
        if v:
            all_ok = False
            for x in v[:10]:
                print(f'    · {x["constraint"]}: {x["detail"]}')
    print('  ' + ('ALL CHECKS PASS' if all_ok else 'FAILURES FOUND'))


if __name__ == '__main__':
    main()
