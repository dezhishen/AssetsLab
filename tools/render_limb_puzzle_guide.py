from __future__ import annotations

import json
import math
import argparse
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "prototype" / "assets" / "characters" / "limb_puzzle.json"
OUTPUT = ROOT / "prototype" / "test_output" / "limb_puzzle_pose_guide_2x4.png"
SCALE = 8
CELL = 64
COLORS = {
    "left_hand": "#5cc8ff",
    "right_hand": "#ff7272",
    "left_foot": "#73e28d",
    "right_foot": "#ffcf60",
}


def rectangle_points(part: dict[str, float]) -> list[tuple[float, float]]:
    angle = math.radians(float(part["angle"]))
    half_width = float(part["w"]) / 2
    half_height = float(part["h"]) / 2
    center_x, center_y = float(part["x"]), float(part["y"])
    points = []
    for local_x, local_y in (
        (-half_width, -half_height),
        (half_width, -half_height),
        (half_width, half_height),
        (-half_width, half_height),
    ):
        x = center_x + math.cos(angle) * local_x - math.sin(angle) * local_y
        y = center_y + math.sin(angle) * local_x + math.cos(angle) * local_y
        points.append((x, y))
    return points


def scaled(points: list[tuple[float, float]], offset_x: int, offset_y: int) -> list[tuple[float, float]]:
    return [(offset_x + x * SCALE, offset_y + y * SCALE) for x, y in points]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if payload.get("schema") != "limb_puzzle_v1" or len(payload.get("frames", [])) != 8:
        raise ValueError("Expected a limb_puzzle_v1 file with eight frames")
    canvas = Image.new("RGB", (CELL * SCALE * 4, CELL * SCALE * 2), "#1b1f2b")
    draw = ImageDraw.Draw(canvas)
    torso = payload.get("torso", {"x": 32, "y": 41.5, "w": 8, "h": 13})
    for index, frame in enumerate(payload["frames"]):
        offset_x = (index % 4) * CELL * SCALE
        offset_y = (index // 4) * CELL * SCALE
        draw.rectangle((offset_x, offset_y, offset_x + CELL * SCALE, offset_y + CELL * SCALE), outline="#3d465f", width=2)
        parts = frame["parts"]
        for name, part in sorted(parts.items(), key=lambda item: item[1]["z_order"]):
            points = scaled(rectangle_points(part), offset_x, offset_y)
            draw.polygon(points, fill=COLORS[name], outline="#151923", width=3)
        torso_box = (
            offset_x + (torso["x"] - torso["w"] / 2) * SCALE,
            offset_y + (torso["y"] - torso["h"] / 2) * SCALE,
            offset_x + (torso["x"] + torso["w"] / 2) * SCALE,
            offset_y + (torso["y"] + torso["h"] / 2) * SCALE,
        )
        draw.rectangle(torso_box, fill="#d4d8e6", outline="#151923", width=3)
        # Repaint foreground parts after the torso, honoring their z-order.
        for name, part in sorted(parts.items(), key=lambda item: item[1]["z_order"]):
            if part["z_order"] > torso.get("z_order", 10):
                points = scaled(rectangle_points(part), offset_x, offset_y)
                draw.polygon(points, fill=COLORS[name], outline="#151923", width=3)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output)
    print(f"LIMB_PUZZLE_GUIDE_PASS output={args.output}")


if __name__ == "__main__":
    main()
