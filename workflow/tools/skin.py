#!/usr/bin/env python3
"""程序化蒙皮引擎：把 atlas 静态分层部件「蒙」到 base.json 骨架上。

皮肤（skin）是一个可替换的绑定定义（workflow/skins/<skin_id>.json）：
部件 -> 关节 + 锚点策略 + 支链。换皮肤只需新建一个 skin 定义并指向对应
部件（atlas），引擎与骨架复用不变。

关键事实：atlas 各层帧是「静态部件」（frame0~frame7 bbox 基本不变），
每层一个固定形状部件（头/躯干/下身/手臂/脚…）。因此蒙皮 = 把静态部件
程序化贴到骨架关节（平移），骨架缩放适配部件尺寸。

每帧流程：
  1) 复用 motion.pose() 采样关节坐标（含体型比例 / root 传导）+ apply_ik
  2) 骨架坐标缩放（scale）到部件尺寸，offset 校准（rest 对齐）
  3) 单侧层：部件锚点对齐其关节；成对层（含左右）：整体贴到各支链关节中点

验证（无需看图）：rest 姿势下「程序化蒙皮」vs「frame 对齐叠加」的 IoU，
越大说明贴合越好。

命令：
  skin list
  skin anchors <atlas_dir> [--skin skeleton] [--view front]
  skin render <motion> --view front --stage arms --skin skeleton --atlas <dir> [--gif out]
  skin verify <atlas_dir> --skin skeleton        # 绑定校验 + rest 贴合 IoU
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SKINS_ROOT = ROOT / "skins"
LEGACY_SKINS = ROOT / "workflow" / "skins"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from motion import BASE, apply_ik, load_motion, pose  # noqa: E402

VIEWS = ("front", "side", "back")
# atlas 行序：front / right / back / left（见 export_artifacts.py）
VIEW_ROW = {"front": 0, "side": 1, "back": 2}
MARGIN = 4
# 锚点策略：从部件包围盒取哪个特征点（部件与主关节重合的参考像素）
POLICIES = ("center", "top_center", "bottom_center")


# ---------------------------------------------------------------- skin io --

def load_skin(skin_id: str) -> dict:
    # 皮肤包：skins/<id>/skin.json（独立目录 + 标准命名部件 <NN>_<layer>_<view>.png）
    pack = SKINS_ROOT / skin_id / "skin.json"
    if pack.exists():
        data = json.loads(pack.read_text(encoding="utf-8"))
        data.setdefault("skin_id", skin_id)
        return data
    # 旧格式：workflow/skins/<id>.json（预烘焙皮肤）
    legacy = LEGACY_SKINS / f"{skin_id}.json"
    if legacy.exists():
        return json.loads(legacy.read_text(encoding="utf-8"))
    raise SystemExit(f"skin not found: {skin_id} ({pack} or {legacy})")


def list_skins() -> list[str]:
    names = {p.parent.name for p in SKINS_ROOT.glob("*/skin.json")}
    names |= {p.stem for p in LEGACY_SKINS.glob("*.json")}
    return sorted(names)


def skin_layers(skin: dict) -> list[str]:
    """皮肤层名列表：皮肤包用 layers（[{name, order}]），旧格式用 atlas_layers。"""
    layers = skin.get("layers")
    if isinstance(layers, list):
        return [l["name"] if isinstance(l, dict) else l for l in layers]
    return skin.get("atlas_layers", [])


def resolve_atlas(skin: dict, atlas_arg: str | Path | None) -> Path:
    """皮肤部件目录。

    - skeleton 坐标皮肤（coordinates="skeleton"）或皮肤包（layout="pack"）：
      程序化固定部件，自包含 atlas_dir，忽略 --atlas 覆盖（工作流传的实例 atlas 不适用）。
    - 预烘焙皮肤：优先 --atlas（如工作流的 dist/<workflow_id>/atlas），
      否则用皮肤定义的 atlas_dir。
    """
    if skin.get("coordinates") == "skeleton" or skin.get("layout") == "pack":
        default = skin.get("atlas_dir")
        if default:
            p = ROOT / default
            if p.is_dir():
                return p
    if atlas_arg:
        return Path(atlas_arg)
    default = skin.get("atlas_dir")
    if default:
        p = ROOT / default
        if p.is_dir():
            return p
    raise SystemExit(f"no atlas given and skin '{skin.get('skin_id')}' has no usable atlas_dir")


def resolve_joint(binding: dict, limb: str | None) -> str:
    joint = binding.get("joint", "")
    return joint % limb if "%s" in joint else joint


# 逻辑关节名 -> 各视图实际关节名（side/back 用 front_ 侧为主侧；front 用 left_ 系
# 别名，因为 walk 预设的 front 偏移驱动 left_hand/left_foot/…）。
# back 视图：手臂用 rear_ 侧（外扩、从背面可见），腿用 front_ 侧（walk back 偏移驱动）。
VIEW_JOINT = {
    ("shoulder_left", "side"): "front_shoulder", ("shoulder_left", "back"): "rear_shoulder_left",
    ("shoulder_right", "side"): "rear_shoulder", ("shoulder_right", "back"): "rear_shoulder_right",
    ("left_elbow", "side"): "front_elbow", ("left_elbow", "back"): "rear_elbow_left",
    ("right_elbow", "side"): "rear_elbow", ("right_elbow", "back"): "rear_elbow_right",
    ("left_hand", "side"): "front_hand", ("left_hand", "back"): "rear_hand_left",
    ("right_hand", "side"): "rear_hand", ("right_hand", "back"): "rear_hand_right",
    # side 视图左右成对层分别绑 front_/rear_（前腿/后腿、前臂/后臂），避免重叠成一条
    ("left_hip", "side"): "front_hip", ("left_hip", "back"): "left_hip",
    ("right_hip", "side"): "rear_hip", ("right_hip", "back"): "right_hip",
    ("left_knee", "side"): "front_knee", ("left_knee", "back"): "left_knee",
    ("right_knee", "side"): "rear_knee", ("right_knee", "back"): "right_knee",
    ("left_foot", "side"): "front_foot", ("left_foot", "back"): "left_foot",
    ("right_foot", "side"): "rear_foot", ("right_foot", "back"): "right_foot",
}


def joint_view(joint: str, view: str) -> str:
    """把逻辑关节名（front 惯例）映射到指定视图的实际关节名。"""
    if view == "front":
        return joint
    return VIEW_JOINT.get((joint, view), joint)


# ---------------------------------------------------------------- anchors --

def bbox_anchor(image: Image.Image, policy: str) -> tuple[int, int]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return (0, 0)
    l, t, r, b = bbox
    cx, cy = (l + r) // 2, (t + b) // 2
    if policy == "top_center":
        return (cx, t)
    if policy == "bottom_center":
        return (cx, b)
    return (cx, cy)


def layer_anchor(skin: dict, layer: str, image: Image.Image) -> tuple[int, int]:
    """锚点优先取皮肤定义 anchors[layer]，否则按 binding 的 anchor_policy 提取。
    skeleton 坐标模式约定：锚点 = 部件图中心（肢体段从中心水平延伸，rotate 绕中心）。"""
    if skin.get("coordinates") == "skeleton":
        return (image.width // 2, image.height // 2)
    stored = skin.get("anchors", {}).get(layer)
    if isinstance(stored, list) and len(stored) == 2:
        return (int(stored[0]), int(stored[1]))
    binding = skin.get("bindings", {}).get(layer, {})
    policy = binding.get("anchor_policy", "center")
    if policy not in POLICIES:
        policy = "center"
    return bbox_anchor(image, policy)


def load_layer_image(skin: dict, layer: str, atlas_dir: Path, view: str) -> Image.Image:
    """取某层在某视图下的部件图。
    皮肤包（layout="pack"）：skins/<id>/<NN>_<layer>_<view>.png（数字序号前缀 + 标准命名）；
    旧格式：<atlas>/<layer>/walk_row<row>_frame0.png。"""
    if skin.get("layout") == "pack":
        base = resolve_atlas(skin, atlas_dir)
        candidates = sorted(base.glob(f"*_{layer}_{view}.png"))
        if not candidates:
            candidates = sorted(base.glob(f"*_{layer}_*.png"))
        if not candidates:
            raise FileNotFoundError(f"no pack image for layer '{layer}' view '{view}' in {base}")
        return Image.open(candidates[0]).convert("RGBA")
    row = VIEW_ROW[view]
    path = atlas_dir / layer / f"walk_row{row}_frame0.png"
    if not path.exists():
        # 回退到任意帧
        candidates = sorted((atlas_dir / layer).glob("*.png"))
        if not candidates:
            raise FileNotFoundError(f"no atlas frames for layer {layer} in {atlas_dir}")
        path = candidates[0]
    return Image.open(path).convert("RGBA")


# ---------------------------------------------------------------- layout --

def joint_images(skin: dict, atlas_dir: Path, view: str) -> dict[str, Image.Image]:
    layers = skin_layers(skin)
    out: dict[str, Image.Image] = {}
    for layer in layers:
        try:
            out[layer] = load_layer_image(skin, layer, atlas_dir, view)
        except FileNotFoundError:
            continue
    return out


def skin_layout(skin: dict, atlas_dir: Path) -> dict:
    """计算骨架->部件画布的缩放与偏移（rest 校准）。

    coordinates="skeleton"：部件按骨架 1:1 坐标绘制（皮肤定义自带 anchors），
    直接映射到 960x600 画布；否则（默认）缩放适配部件尺寸。
    """
    if skin.get("coordinates") == "skeleton":
        return {
            "scale": 1.0, "ox": 0.0, "oy": 0.0,
            "canvas_w": 960, "canvas_h": 600,
            "origin_x": 0, "origin_y": 0,
        }
    images = joint_images(skin, atlas_dir, "front")
    boxes = [im.getchannel("A").getbbox() for im in images.values()]
    boxes = [b for b in boxes if b]
    pl = min(b[0] for b in boxes)
    pt = min(b[1] for b in boxes)
    pr = max(b[2] for b in boxes)
    pb = max(b[3] for b in boxes)
    part_h = pb - pt
    part_w = pr - pl

    base = BASE.get("front", {})
    skel_top = min(j[1] for j in base.values())
    skel_bot = max(j[1] for j in base.values())
    skel_h = skel_bot - skel_top
    scale = part_h / skel_h if skel_h else 1.0

    pelvis = base.get("pelvis", (0, 0))
    sx, sy = pelvis[0] * scale, pelvis[1] * scale
    lb = images.get("lower_body")
    if lb is not None and lb.getchannel("A").getbbox():
        bb = lb.getchannel("A").getbbox()
        pxx, pxy = (bb[0] + bb[2]) // 2, bb[3]
    else:
        pxx, pxy = part_w // 2, pb
    ox, oy = pxx - sx, pxy - sy
    return {
        "scale": scale, "ox": ox, "oy": oy,
        "canvas_w": part_w + MARGIN * 2, "canvas_h": part_h + MARGIN * 2,
        "origin_x": pl - MARGIN, "origin_y": pt - MARGIN,
    }


def to_canvas(joint: tuple, layout: dict) -> tuple[int, int]:
    """骨架关节坐标 -> 部件画布坐标（缩放 + 偏移 + 原点平移）。"""
    x = joint[0] * layout["scale"] + layout["ox"] - layout["origin_x"]
    y = joint[1] * layout["scale"] + layout["oy"] - layout["origin_y"]
    return (round(x), round(y))


def rest_ref(skin: dict, atlas_dir: Path, view: str) -> Image.Image:
    """frame 对齐叠加 = 各层静态部件在预烘焙位置的完整角色（参考真值）。
    skeleton 坐标模式部件相互独立，此参考不适用（verify 会走专门分支）。"""
    if skin.get("coordinates") == "skeleton":
        return Image.new("RGBA", (960, 600), (0, 0, 0, 0))
    images = joint_images(skin, atlas_dir, view)
    layout = skin_layout(skin, atlas_dir)
    canvas = Image.new("RGBA", (layout["canvas_w"], layout["canvas_h"]), (0, 0, 0, 0))
    for layer in skin_layers(skin):
        img = images.get(layer)
        if img is None:
            continue
        canvas.alpha_composite(img, (-layout["origin_x"], -layout["origin_y"]))
    return canvas


# ---------------------------------------------------------------- render --

def rotate_to_joint(image: Image.Image, anchor: tuple[int, int],
                    joint: tuple[int, int], child: tuple[int, int]) -> Image.Image:
    """把「从锚点水平延伸」的部件绕锚点旋转，使其指向 关节->子关节 方向。
    部件图约定：锚点在图中心，段从锚点沿 +x 水平延伸（base_angle=0）。
    PIL rotate(+θ) 把 +x 段转向 -y（屏幕上方）；要指向屏幕角 φ=atan2(dy,dx)
    （y 向下为正）需 rotate(-φ)。"""
    dx = child[0] - joint[0]
    dy = child[1] - joint[1]
    deg = math.degrees(math.atan2(dy, dx))
    return image.rotate(-deg, center=anchor, resample=Image.Resampling.NEAREST)

def skin_frame(motion: dict, view: str, stage: str, index: int,
               params: dict | None, proportions: dict | None,
               skin: dict, atlas_dir: Path, layout: dict,
               only_layers: list[str] | None = None) -> Image.Image:
    """渲染一帧蒙皮。only_layers 传层名列表则只渲染这些层（供制品分层烘焙）。"""
    coords = pose(motion, view, stage, index, params, proportions)
    apply_ik(motion, view, stage, coords)
    canvas = Image.new("RGBA", (layout["canvas_w"], layout["canvas_h"]), (0, 0, 0, 0))
    images = joint_images(skin, atlas_dir, view)
    for layer in skin_layers(skin):
        if only_layers is not None and layer not in only_layers:
            continue
        binding = skin.get("bindings", {}).get(layer)
        img = images.get(layer)
        if img is None or binding is None:
            continue
        anchor = layer_anchor(skin, layer, img)
        limbs = binding.get("limb")
        if limbs:
            # 成对层（arms/feet）：整体贴到各支链关节的中点
            pts = []
            for limb in limbs.split("/"):
                jc = coords.get(resolve_joint(binding, limb))
                if jc is not None:
                    pts.append(to_canvas(jc, layout))
            if not pts:
                continue
            cx = sum(p[0] for p in pts) // len(pts)
            cy = sum(p[1] for p in pts) // len(pts)
            canvas.alpha_composite(img, (cx - anchor[0], cy - anchor[1]))
        else:
            joint_name = joint_view(resolve_joint(binding, None), view)
            jc = coords.get(joint_name)
            if jc is None:
                continue
            pos = to_canvas(jc, layout)
            piece = img
            child = binding.get("rotate_child")
            if child:
                cc = coords.get(joint_view(child, view))
                if cc is not None:
                    piece = rotate_to_joint(img, anchor, pos, to_canvas(cc, layout))
            canvas.alpha_composite(piece, (pos[0] - anchor[0], pos[1] - anchor[1]))
    return canvas


def render_gif(motion_id: str, view: str, stage: str, skin_id: str, atlas_dir: Path,
               params: dict | None, proportions: dict | None, out: Path) -> None:
    motion = load_motion(motion_id)
    skin = load_skin(skin_id)
    layout = skin_layout(skin, atlas_dir)
    frame_count = int(motion.get("frame_count", 8))
    frames = [skin_frame(motion, view, stage, i, params, proportions, skin, atlas_dir, layout)
              for i in range(frame_count)]
    w, h = layout["canvas_w"], layout["canvas_h"]
    enlarged = [f.resize((w * 4, h * 4), Image.Resampling.NEAREST) for f in frames]
    out.parent.mkdir(parents=True, exist_ok=True)
    # disposal=2 (restore to background): 每帧先清空再绘制，避免透明背景的
    # 后一帧叠在之前帧上（残影/重叠）。
    enlarged[0].save(out, format="GIF", save_all=True, append_images=enlarged[1:],
                     duration=125, loop=0, disposal=2)
    # 同时输出 PNG 帧序列（供 Godot 运行时蒙皮预览 / 外部查看）
    frame_dir = out.with_suffix("")
    frame_dir.mkdir(parents=True, exist_ok=True)
    for i, f in enumerate(enlarged):
        f.save(frame_dir / f"frame{i}.png")
    print(f"SKIN_GIF_PASS skin={skin_id} motion={motion_id} view={view} stage={stage} "
          f"canvas={w}x{h} -> {out}")


# --------------------------------------------------------------------- cli --

def cmd_list(_args: argparse.Namespace) -> int:
    for name in list_skins():
        print(name)
    return 0


def cmd_anchors(args: argparse.Namespace) -> int:
    skin = load_skin(args.skin)
    atlas_dir = resolve_atlas(skin, args.atlas)
    view = args.view
    out: dict[str, list[int]] = {}
    for layer in skin_layers(skin):
        try:
            img = load_layer_image(skin, layer, atlas_dir, view)
        except FileNotFoundError:
            continue
        out[layer] = list(layer_anchor(skin, layer, img))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    params = {}
    for item in args.param or []:
        if "=" in item:
            k, v = item.split("=", 1)
            params[k] = float(v)
    proportions = {}
    for item in args.body or []:
        if "=" in item:
            k, v = item.split("=", 1)
            proportions[k] = float(v)
    out = Path(args.gif) if args.gif else (ROOT / "skins" / args.skin / "preview"
                                           / f"{args.skin}_{args.motion}_{args.view}.gif")
    skin = load_skin(args.skin)
    render_gif(args.motion, args.view, args.stage, args.skin, resolve_atlas(skin, args.atlas),
               params or None, proportions or None, out)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    skin = load_skin(args.skin)
    atlas_dir = resolve_atlas(skin, args.atlas)
    errors = []
    for view in VIEWS:
        for layer in skin_layers(skin):
            try:
                img = load_layer_image(skin, layer, atlas_dir, view)
                if not img.getchannel("A").getbbox():
                    # 某些视角某些层本来无内容（如背面脸层）——提示而非错误
                    print(f"  [i] {view}/{layer}: empty alpha (expected for some views)")
            except FileNotFoundError:
                errors.append(f"{view}/{layer}: missing atlas frame")

    # 贴合验证
    layout = skin_layout(skin, atlas_dir)
    print(f"  [i] layout: scale={layout['scale']:.3f} "
          f"canvas={layout['canvas_w']}x{layout['canvas_h']} coords={skin.get('coordinates', 'normalized')}")
    if skin.get("coordinates") == "skeleton":
        # skeleton 坐标：锚点=图中心精确贴关节。校验关节映射完整性 + 渲染 rest 合成帧。
        base = BASE
        out_dir = ROOT / "prototype" / "test_output" / "skeleton_pipeline"
        out_dir.mkdir(parents=True, exist_ok=True)
        problems = []
        for view in VIEWS:
            joints = base.get(view, {})
            motion = load_motion("idle")
            skinned = skin_frame(motion, view, "arms", 0, None, None, skin, atlas_dir, layout)
            out_png = out_dir / f"skin_{args.skin}_rest_{view}.png"
            skinned.save(out_png)
            bb = skinned.getchannel("A").getbbox()
            missing: list[str] = []
            for layer in skin_layers(skin):
                binding = skin.get("bindings", {}).get(layer)
                if not binding:
                    continue
                for ref in [resolve_joint(binding, None), binding.get("rotate_child")]:
                    if not ref:
                        continue
                    if joint_view(ref, view) not in joints:
                        missing.append(f"{layer}->{ref}")
            if missing:
                problems.append(f"{view}: missing joints {missing}")
            print(f"  [i] {view}: rest composite bbox={bb} -> {out_png}")
        if problems:
            for p in problems:
                print(f"  [x] {p}")
            return 1
    else:
        # 归一化坐标：程序化蒙皮 vs frame 对齐参考（IoU 越大贴合越好）
        for view in VIEWS:
            ref = rest_ref(skin, atlas_dir, view)
            motion = load_motion("walk")
            skinned = skin_frame(motion, view, "arms", 0, None, None, skin, atlas_dir, layout)
            ref_a = ref.getchannel("A")
            sk_a = skinned.getchannel("A")
            ref_px = {(x, y) for x in range(ref.width) for y in range(ref.height)
                      if ref_a.getpixel((x, y)) > 0}
            sk_px = {(x, y) for x in range(skinned.width) for y in range(skinned.height)
                     if sk_a.getpixel((x, y)) > 0}
            union = ref_px | sk_px
            inter = ref_px & sk_px
            iou = len(inter) / len(union) if union else 1.0
            print(f"  [i] {view}: rest-skin IoU vs frame-align = {iou:.3f} "
                  f"(ref_px={len(ref_px)} skin_px={len(sk_px)})")
    if errors:
        for e in errors:
            print(f"  [x] {e}")
        return 1
    print(f"SKIN_VERIFY_PASS skin={args.skin} layers={len(skin_layers(skin))} views={len(VIEWS)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AssetsLab procedural skinning engine (skin a layered atlas onto the skeleton).")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List available skins.").set_defaults(handler=cmd_list)
    p = sub.add_parser("anchors", help="Extract per-layer anchors from an atlas.")
    p.add_argument("atlas", nargs="?", default=None, help="Atlas directory (default: skin.atlas_dir).")
    p.add_argument("--skin", default="skeleton")
    p.add_argument("--view", choices=VIEWS, default="front")
    p.set_defaults(handler=cmd_anchors)
    p = sub.add_parser("render", help="Render a skinned motion frame/GIF.")
    p.add_argument("motion", help="Motion preset id (walk/run/idle/jump).")
    p.add_argument("--view", choices=VIEWS, required=True)
    p.add_argument("--stage", choices=("skeleton", "legs", "pelvis", "arms"), default="arms")
    p.add_argument("--skin", default="skeleton")
    p.add_argument("--atlas", default=None, help="Atlas directory (default: skin.atlas_dir).")
    p.add_argument("--param", action="append", metavar="NAME=VALUE")
    p.add_argument("--body", action="append", metavar="NAME=VALUE")
    p.add_argument("--gif", type=Path, help="Output GIF path (default: prototype/test_output/skeleton_pipeline/).")
    p.set_defaults(handler=cmd_render)
    p = sub.add_parser("verify", help="Verify a skin's bindings/anchors against an atlas (incl. rest-skin IoU).")
    p.add_argument("atlas", nargs="?", default=None, help="Atlas directory (default: skin.atlas_dir).")
    p.add_argument("--skin", default="skeleton")
    p.set_defaults(handler=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
