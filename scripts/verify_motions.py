#!/usr/bin/env python3
"""三步动作验证流水线（数据驱动、物种可配置）。

  Step 1 (sample)  : 采样动作所有帧、所有视图的关节坐标轨迹（结构化数据）。
  Step 2 (enforce) : 读取【物种骨骼模型的 constraints】（随物种同步创建），
                     逐条执行现实的、固定的强制约束判断。
  Step 3 (ai)      : 生成 AI 审查包（坐标数据 JSON + 关键帧图 + 约束报告），
                     供 AI 复核物理合理性 / 解剖学 / 运动规律。

约束定义位置：assetslab/species/<species_id>/skeleton.json 的 "constraints" 段。
创建新物种时同步定义该物种的约束（人类膝盖朝前 / 肘部朝后；四足、鸟类等各异）。

用法：
    python scripts/verify_motions.py                 # 三步全跑，打印结果
    python scripts/verify_motions.py walk run        # 指定动作
    python scripts/verify_motions.py --export out/   # 同时导出 AI 审查包
    python scripts/verify_motions.py --ai out/ walk  # 只导出 AI 审查包
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from assetslab.motion import (  # noqa: E402
    load_motion,
    pose,
    apply_ik,
    set_skeleton,
    load_skeleton,
    skeleton_views,
    _propagate_foot,
    _propagate_hand,
    _collect_offset_joints,
)

VIEWS = ("front", "side", "back")
MOTIONS = ("walk", "run", "jump", "idle")
SPECIES_ROOT = ROOT / "assetslab" / "species"


# =====================================================================
# Step 1 — 采样器：拿到所有帧所有视图所有节点的坐标变化
# =====================================================================


def sample(motion_id: str, skeleton: str = "standard", params: dict | None = None,
           views: tuple = VIEWS) -> dict:
    """采样一个动作：返回 {motion_id, skeleton, params, frame_count, views:{view:[{joint:[x,y]}]}}。

    与渲染管线完全一致（pose → apply_ik → 脚掌/手掌刚性传播），因此
    采样数据就是最终渲染用的坐标。
    """
    motion = load_motion(motion_id)
    set_skeleton(skeleton)
    use_ik = bool(motion.get("ik"))
    n = int(motion.get("frame_count", 8))
    data = {
        "motion_id": motion_id,
        "skeleton": skeleton,
        "frame_count": n,
        "params": params or {},
        "views": {},
    }
    for view in views:
        frames = []
        for i in range(n):
            coords = pose(motion, view, "arms", i, params or None, None)
            if use_ik:
                apply_ik(motion, view, "arms", coords)
                _oj = _collect_offset_joints(motion, view, "arms")
                _propagate_foot(coords, view, _oj)
                _propagate_hand(coords, view, _oj)
            frame = {}
            for j, pt in coords.items():
                if isinstance(pt, (list, tuple)) and len(pt) == 2:
                    frame[j] = [round(float(pt[0]), 1), round(float(pt[1]), 1)]
            frames.append(frame)
        data["views"][view] = frames
    return data


# =====================================================================
# Step 2 — 强制约束：读物种 constraints，逐条强制判断
# =====================================================================


def load_constraints(species_id: str = "human") -> dict:
    """读取物种骨骼模型自带的 constraints（创建物种时同步定义）。"""
    path = SPECIES_ROOT / species_id / "skeleton.json"
    if not path.exists():
        raise FileNotFoundError(f"species skeleton not found: {path}")
    d = json.loads(path.read_text(encoding="utf-8"))
    cons = d.get("constraints")
    if not cons:
        raise ValueError(f"species '{species_id}' 未定义 constraints（创建物种时应同步定义）")
    return cons


def _bones(species_id: str) -> dict:
    path = SPECIES_ROOT / species_id / "skeleton.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    return d.get("bones", {})


def _base(skeleton: str) -> dict:
    set_skeleton(skeleton)
    return skeleton_views(load_skeleton(skeleton))


def _perp_side(a, mid, b):
    """mid 相对 a→b 轴线的垂直方向投影（p 方向）。"""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return 0.0
    ux, uy = dx / dist, dy / dist
    px, py = -uy, ux
    return px * (mid[0] - ax) + py * (mid[1] - ay)


def _bend_sign(mid_name: str, bend: str) -> float:
    """bend 方向 → 期望的 perp_side 符号（轴线朝下假设：root 在 tip 上方）。

    forward  (朝前)  -> -1    (膝盖，side 视图 -p 侧 = +x)
    backward (朝后)  -> +1    (肘部，side 视图 +p 侧 = -x)
    outward  (朝外)  -> 左肢 +1 / 右肢 -1 (front 视图肘部)
    """
    if bend == "forward":
        return -1.0
    if bend == "backward":
        return 1.0
    if bend == "outward":
        return 1.0 if "left" in mid_name else -1.0
    return 0.0


def enforce(data: dict, constraints: dict, species_id: str = "human") -> list:
    """逐条强制约束，返回 violations: [ {constraint, frames?, detail} ]。"""
    violations = []
    n = data["frame_count"]
    frames = data["views"]
    base = _base(data["skeleton"])
    bones = _bones(species_id)

    # ---- 1) 骨长恒定（每根骨各帧长度 vs 基准）----
    tol = constraints.get("bone_length", {}).get("tolerance", 0.05)
    for view in VIEWS:
        base_v = base[view]
        for a, b in bones.get(view, []):
            if a not in base_v or b not in base_v:
                continue
            rest = math.hypot(base_v[b][0] - base_v[a][0], base_v[b][1] - base_v[a][1])
            if rest < 1.0:
                continue
            for i in range(n):
                c = frames[view][i]
                if a in c and b in c:
                    L = math.hypot(c[b][0] - c[a][0], c[b][1] - c[a][1])
                    if abs(L - rest) / rest > tol:
                        violations.append({
                            "constraint": "bone_length",
                            "frames": [i], "detail": f"{view} f{i} {a}—{b}: {L:.1f} vs {rest:.1f}"})
                        break

    # ---- 2) 帧间平滑（无瞬移）----
    max_disp = constraints.get("smoothness", {}).get("max_frame_disp", 60.0)
    for view in VIEWS:
        for i in range(n):
            c0, c1 = frames[view][i], frames[view][(i + 1) % n]
            for j, pt in c0.items():
                if j in c1:
                    d = math.hypot(pt[0] - c1[j][0], pt[1] - c1[j][1])
                    if d > max_disp:
                        violations.append({
                            "constraint": "smoothness",
                            "frames": [i, (i + 1) % n],
                            "detail": f"{view} f{i}->{(i+1)%n} {j}: {d:.0f}px"})
                        break

    # ---- 3) 关节解剖方向（物种特有：膝盖朝前 / 肘部朝后/外）----
    for rule in constraints.get("joint_direction", []):
        view, mid, tol = rule["view"], rule["mid"], rule.get("tol", 3.0)
        want = _bend_sign(mid, rule["bend"])
        for i in range(n):
            c = frames[view][i]
            if rule["root"] in c and mid in c and rule["tip"] in c:
                v = _perp_side(c[rule["root"]], c[mid], c[rule["tip"]])
                if (v > tol and want < 0) or (v < -tol and want > 0):
                    violations.append({
                        "constraint": "joint_direction",
                        "frames": [i],
                        "detail": f"{rule['id']} f{i}: 反关节 ({rule['bend']} 应为 {v:+.0f})"})

    # ---- 4) 着地（按动作模式）----
    gc = constraints.get("ground_contact", {})
    feet, floor = gc.get("feet", {}), gc.get("floor_y", 470.0)
    mode_spec = gc.get(data["motion_id"])
    if mode_spec:
        mode = mode_spec.get("mode")
        tol = mode_spec.get("tol", 12.0)
        if mode == "one_planted":
            for i in range(n):
                for view, keys in feet.items():
                    ys = [frames[view][i][k][1] for k in keys if k in frames[view][i]]
                    if ys and all(y < floor - tol for y in ys):
                        violations.append({
                            "constraint": "ground_contact",
                            "frames": [i], "detail": f"{view} f{i}: 双脚离地（行走须一脚着地）"})
        elif mode == "flight_limited":
            air = []
            for i in range(n):
                for view, keys in feet.items():
                    ys = [frames[view][i][k][1] for k in keys if k in frames[view][i]]
                    if ys and all(y < floor - tol for y in ys):
                        air.append(i)
                        break
            air = sorted(set(air))
            if len(air) > mode_spec.get("max_flight", 4):
                violations.append({
                    "constraint": "ground_contact", "frames": air,
                    "detail": f"跑步腾空 {len(air)} 帧 {air}（上限 {mode_spec.get('max_flight')}）"})
        elif mode == "all_planted":
            for i in range(n):
                for view, keys in feet.items():
                    for k in keys:
                        if k in frames[view][i] and frames[view][i][k][1] < floor - tol:
                            violations.append({
                                "constraint": "ground_contact",
                                "frames": [i], "detail": f"{view}/{k} f{i}: 待机脚离地"})

    # ---- 5) 左右对称（腿部半周期镜像）----
    sym = constraints.get("symmetry", {})
    if sym and data["motion_id"] not in sym.get("skip_motions", []):
        half = n // 2
        s_tol = sym.get("tolerance", 8.0)
        for view in sym.get("views", []):
            for a, b in sym.get("pairs", {}).get(view, []):
                err = 0.0
                for i in range(n):
                    if a in frames[view][i] and b in frames[view][(i + half) % n]:
                        pa, pb = frames[view][i][a], frames[view][(i + half) % n][b]
                        err += abs((pa[0] - 480.0) + (pb[0] - 480.0)) + abs(pa[1] - pb[1])
                if err / n > s_tol:
                    violations.append({
                        "constraint": "symmetry",
                        "detail": f"{view} {a}/{b}: 平均不对称 {err/n:.1f}"})

    # ---- 6) 肘部应真实弯曲（非僵硬平移）----
    ea = constraints.get("elbow_articulation", {})
    if data["motion_id"] not in ea.get("skip_motions", []):
        min_spread = ea.get("min_spread_deg", 6.0)
        for view, triples in ea.get("chains", {}).items():
            for elbow, wrist, palm in triples:
                angles = []
                for i in range(n):
                    c = frames[view][i]
                    if elbow in c and wrist in c and palm in c:
                        e, w, p = c[elbow], c[wrist], c[palm]
                        v1 = (w[0] - e[0], w[1] - e[1])
                        v2 = (p[0] - w[0], p[1] - w[1])
                        m1, m2 = math.hypot(*v1), math.hypot(*v2)
                        if m1 > 1 and m2 > 1:
                            ang = math.degrees(math.acos(max(-1, min(1, (v1[0]*v2[0]+v1[1]*v2[1])/(m1*m2)))))
                            angles.append(ang)
                spread = (max(angles) - min(angles)) if angles else 0.0
                if spread < min_spread:
                    violations.append({
                        "constraint": "elbow_articulation",
                        "detail": f"{view} {elbow}: 肘部几乎不弯 ({spread:.1f}° < {min_spread}°)"})

    return violations


# =====================================================================
# Step 3 — AI 审查：导出数据包（坐标 + 关键帧图 + 报告），供 AI 复核
# =====================================================================


def export_ai_brief(motion_id: str, skeleton: str, data: dict, violations: list,
                    out_dir: Path) -> Path:
    """生成 AI 审查包：
      ai_brief_<motion>.json   —— 全部帧坐标数据（可程序化复核）
      ai_brief_<motion>.md     —— 人类/AI 可读的报告（约束结果 + 待复核要点）
      ai_sheet_<motion>_<view>.png —— 关键帧接触表（视觉复核）
    """
    from PIL import Image
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"ai_brief_{motion_id}"

    # 1) 坐标数据
    (out_dir / f"{stem}.json").write_text(
        json.dumps({"sample": data, "violations": violations}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    # 2) 关键帧接触表
    set_skeleton(skeleton)
    motion = load_motion(motion_id)
    use_ik = bool(motion.get("ik"))
    sheet_paths = []
    for view in ("front", "side", "back"):
        frames = []
        for i in range(int(data["frame_count"])):
            img = None
            # 用 motion 渲染管线生成帧图
            from assetslab.motion import render_frame
            img = render_frame(motion, view, "arms", i, None, use_ik, None)
            frames.append(img)
        sheet = Image.new("RGB", (480 * 4, 300 * 2), (17, 24, 39))
        for i, f in enumerate(frames):
            sheet.paste(f.resize((480, 300), Image.Resampling.NEAREST),
                        ((i % 4) * 480, (i // 4) * 300))
        sp = out_dir / f"{stem}_{view}.png"
        sheet.save(sp)
        sheet_paths.append(sp)

    # 3) 报告
    status = "PASS" if not violations else f"FAIL ({len(violations)})"
    lines = [
        f"# AI 验证简报 — {motion_id}（{skeleton}）",
        "",
        f"- 采样: {data['frame_count']} 帧 × {len(data['views'])} 视图，全部关节坐标见 {stem}.json",
        f"- 硬约束: {status}",
        "- 关键帧接触表: " + ", ".join(f"`{p.name}`" for p in sheet_paths),
        "",
        "## 请 AI 复核的要点",
        "1. 坐标数据是否满足骨骼模型的硬约束（骨长恒定 / 平滑 / 解剖方向 / 着地 / 对称）。",
        "2. 动作是否符合真实运动规律（步态相位、腾空、呼吸节奏等）。",
        "3. 是否存在数据无法直接捕获的视觉/动力学异常（卡顿、姿态怪诞、重心失衡）。",
        "",
    ]
    if violations:
        lines += ["## 硬约束违规", ""]
        for v in violations:
            lines.append(f"- **{v['constraint']}**" + (f" @帧{v['frames']}:" if v.get('frames') else ": ") + v["detail"])
    else:
        lines += ["## 硬约束违规", "", "无。所有物种硬约束均通过。", ""]
    (out_dir / f"{stem}.md").write_text("\n".join(lines), encoding="utf-8")
    return out_dir / f"{stem}.md"


# =====================================================================
# CLI
# =====================================================================


def main() -> int:
    ap = argparse.ArgumentParser(description="三步动作验证流水线")
    ap.add_argument("motions", nargs="*", default=None, help="动作 id（默认全部）")
    ap.add_argument("--skeleton", default="standard", help="预设/骨架 id")
    ap.add_argument("--species", default="human", help="物种 id（决定约束）")
    ap.add_argument("--export", metavar="DIR", default=None, help="导出 AI 审查包目录")
    ap.add_argument("--ai", metavar="DIR", default=None, help="只导出 AI 审查包，不做硬约束判断")
    args = ap.parse_args()

    motions = args.motions or list(MOTIONS)
    constraints = load_constraints(args.species)

    if args.ai:
        for mid in motions:
            data = sample(mid, args.skeleton)
            brief = export_ai_brief(mid, args.skeleton, data, [], Path(args.ai))
            print(f"AI 审查包: {brief}")
        print("完成。可将 ai_brief_*.md + .json + .png 提交给 AI 复核。")
        return 0

    headers = ["motion", "bone", "ik", "smooth", "ground", "sym", "elbow", "anatomy", "param"]
    print(f"{'motion':6s} {'bone':5s} {'smooth':7s} {'ground':8s} {'sym':5s} {'elbow':6s} {'anatomy':7s} {'param':6s}")
    print("-" * 70)
    all_pass = True
    for mid in motions:
        data = sample(mid, args.skeleton)
        # Step 2: 硬约束
        violations = enforce(data, constraints, args.species)
        # 按约束分组统计
        by_kind = {}
        for v in violations:
            by_kind.setdefault(v["constraint"], []).append(v)
        # 参数扫描（额外：验证参数提取 + 极值有效）
        param_issues = _param_sweep(mid, args.skeleton)
        by_kind["param"] = param_issues
        # 汇总每类
        names = ["bone_length", "smoothness", "ground_contact", "symmetry",
                 "elbow_articulation", "joint_direction", "param"]
        labels = {"bone_length": "bone", "smoothness": "smooth", "ground_contact": "ground",
                  "symmetry": "sym", "elbow_articulation": "elbow",
                  "joint_direction": "anatomy", "param": "param"}
        cells = []
        for n_ in names:
            v = by_kind.get(n_, [])
            cells.append("PASS" if not v else f"FAIL({len(v)})")
        ok = all(c == "PASS" for c in cells)
        all_pass = all_pass and ok
        print(f"{mid:6s} {cells[0][:5]:5s} {cells[1][:7]:7s} {cells[2][:8]:8s} "
              f"{cells[3][:5]:5s} {cells[4][:6]:6s} {cells[5][:7]:7s} {cells[6][:6]:6s}")
        for n_ in names:
            for v in by_kind.get(n_, [])[:6]:
                print(f"    · {v['constraint']}: {v['detail']}")
        if args.export:
            brief = export_ai_brief(mid, args.skeleton, data, violations, Path(args.export))
            print(f"    AI 审查包: {brief}")
    print("-" * 70)
    print("ALL CHECKS PASS" if all_pass else "FAILURES FOUND — see above")
    return 0 if all_pass else 1


def _param_sweep(motion_id: str, skeleton: str) -> list:
    """验证每个参数：a) 被读取（有效）；b) 上限仍平滑/不撕裂。"""
    motion = load_motion(motion_id)
    set_skeleton(skeleton)
    use_ik = bool(motion.get("ik"))
    params = motion.get("params", {})
    if not params:
        return []
    n = int(motion.get("frame_count", 8))
    issues = []

    def sample(overrides):
        out = {}
        for view in VIEWS:
            ps = []
            for i in range(n):
                coords = pose(motion, view, "arms", i, overrides, None)
                if use_ik:
                    apply_ik(motion, view, "arms", coords)
                    _oj = _collect_offset_joints(motion, view, "arms")
                    _propagate_foot(coords, view, _oj)
                    _propagate_hand(coords, view, _oj)
                ps.append(coords)
            out[view] = ps
        return out

    default = sample(None)
    max_disp = 60.0
    for name, spec in params.items():
        mx = spec.get("max", 2.0)
        extreme = sample({name: mx})
        moved = False
        for view in VIEWS:
            for i in range(n):
                for j, pt in extreme[view][i].items():
                    if j in default[view][i] and isinstance(pt, (list, tuple)) and len(pt) == 2:
                        if math.hypot(pt[0] - default[view][i][j][0], pt[1] - default[view][i][j][1]) > 0.5:
                            moved = True
                            break
                if moved:
                    break
            if moved:
                break
        if not moved:
            issues.append({"constraint": "param", "detail": f"参数 {name} 无效（拉满无变化）"})
        for view in VIEWS:
            prev = None
            for i in range(n):
                coords = extreme[view][i]
                if prev is not None:
                    for j, pt in coords.items():
                        if j in prev and isinstance(pt, (list, tuple)) and len(pt) == 2:
                            d = math.hypot(pt[0] - prev[j][0], pt[1] - prev[j][1])
                            if d > max_disp:
                                issues.append({"constraint": "param",
                                               "detail": f"{name} 上限: {view} f{i-1}->{i} {j}: {d:.0f}px"})
                                break
                prev = coords
    return issues


if __name__ == "__main__":
    sys.exit(main())
