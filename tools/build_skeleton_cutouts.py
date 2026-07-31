from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "prototype/assets/characters/generated/body_outline_split_v2_manual_from_project/frame0.png"
POSE = ROOT / "prototype/assets/characters/generated/skeleton_workflows/A_both_legs_pass.json"
OUTPUT = ROOT / "prototype/assets/characters/generated/skeleton_workflows/cutouts"


def rectangle_points(part: dict[str, float]) -> list[tuple[float, float]]:
    angle = math.radians(float(part["angle"]))
    half_width = float(part["w"]) / 2.0
    half_height = float(part["h"]) / 2.0
    center_x = float(part["x"])
    center_y = float(part["y"])
    points = []
    for local_x, local_y in (
        (-half_width, -half_height),
        (half_width, -half_height),
        (half_width, half_height),
        (-half_width, half_height),
    ):
        points.append(
            (
                center_x + math.cos(angle) * local_x - math.sin(angle) * local_y,
                center_y + math.sin(angle) * local_x + math.cos(angle) * local_y,
            )
        )
    return points


def part_mask(size: tuple[int, int], part: dict[str, float]) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon(rectangle_points(part), fill=255)
    return mask.filter(ImageFilterMax())


def ImageFilterMax():
    # Kept as a function so the intent is visible at the call site and Pillow
    # imports remain small for the standalone asset tool.
    from PIL import ImageFilter

    return ImageFilter.MaxFilter(3)


def main() -> int:
    source = Image.open(SOURCE).convert("RGBA")
    payload = json.loads(POSE.read_text(encoding="utf-8"))
    parts = payload["frames"][0]["parts"]
    alpha = source.getchannel("A")
    masks = {name: part_mask(source.size, part) for name, part in parts.items()}

    OUTPUT.mkdir(parents=True, exist_ok=True)
    combined = Image.new("L", source.size, 0)
    for mask in masks.values():
        combined = ImageChops.lighter(combined, mask)
    core_alpha = ImageChops.subtract(alpha, combined)
    core = source.copy()
    core.putalpha(core_alpha)
    core.save(OUTPUT / "core.png")

    registrations = {}
    for name, mask in masks.items():
        alpha_part = ImageChops.multiply(alpha, mask)
        bbox = alpha_part.getbbox()
        if bbox is None:
            raise ValueError(f"empty cutout for {name}")
        image = source.crop(bbox).convert("RGBA")
        image.putalpha(alpha_part.crop(bbox))
        image.save(OUTPUT / f"{name}.png")
        part = parts[name]
        registrations[name] = {
            "source_bbox": list(bbox),
            "source_center": [float(part["x"]), float(part["y"])],
            "source_angle": float(part["angle"]),
            "z_order": int(part["z_order"]),
        }

    manifest = {
        "schema": "skeleton_cutouts_v1",
        "source_art": SOURCE.relative_to(ROOT).as_posix(),
        "source_pose": POSE.relative_to(ROOT).as_posix(),
        "cell_size": [64, 64],
        "core": "core.png",
        "parts": registrations,
        "notes": "Rigid cutouts for Skeleton2D workflow comparison; not a final production split.",
    }
    (OUTPUT / "cutouts_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"SKELETON_CUTOUTS_PASS parts={len(registrations)} output={OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
