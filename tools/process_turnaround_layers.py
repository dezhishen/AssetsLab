from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "prototype" / "assets" / "characters" / "generated" / "character_turnaround_v1_male.png"
OUTPUT = ROOT / "prototype" / "assets" / "characters" / "turnaround_v1"
CELL_SIZE = 256
ROWS = 2
COLUMNS = 2
DIRECTIONS = ["front", "right", "back", "left"]
TARGET_HEIGHT = 232
BASELINE_Y = 244


def is_magenta(red: int, green: int, blue: int) -> bool:
    return red > 150 and blue > 120 and green < 105 and red + blue - 2 * green > 200


def foreground_mask(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    mask = Image.new("L", rgb.size, 0)
    source = rgb.load()
    target = mask.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            if not is_magenta(*source[x, y]):
                target[x, y] = 255
    return mask


def component_boxes(mask: Image.Image, minimum: int = 8) -> list[tuple[int, tuple[int, int, int, int]]]:
    width, height = mask.size
    pixels = mask.load()
    visited: set[tuple[int, int]] = set()
    result: list[tuple[int, tuple[int, int, int, int]]] = []
    for y in range(height):
        for x in range(width):
            if (x, y) in visited or pixels[x, y] == 0:
                continue
            queue = deque([(x, y)])
            visited.add((x, y))
            points: list[tuple[int, int]] = []
            while queue:
                px, py = queue.popleft()
                points.append((px, py))
                for nx in range(px - 1, px + 2):
                    for ny in range(py - 1, py + 2):
                        if 0 <= nx < width and 0 <= ny < height:
                            if (nx, ny) not in visited and pixels[nx, ny] > 0:
                                visited.add((nx, ny))
                                queue.append((nx, ny))
            if len(points) >= minimum:
                xs = [point[0] for point in points]
                ys = [point[1] for point in points]
                result.append((len(points), (min(xs), min(ys), max(xs) + 1, max(ys) + 1)))
    return sorted(result, reverse=True)


def color_mask(image: Image.Image, predicate, region: tuple[int, int, int, int]) -> Image.Image:
    rgb = image.convert("RGB")
    mask = Image.new("L", rgb.size, 0)
    source = rgb.load()
    target = mask.load()
    x0, y0, x1, y1 = region
    for y in range(max(0, y0), min(rgb.height, y1)):
        for x in range(max(0, x0), min(rgb.width, x1)):
            if predicate(*source[x, y]):
                target[x, y] = 255
    return mask


def union_masks(*masks: Image.Image) -> Image.Image:
    result = Image.new("L", masks[0].size, 0)
    for mask in masks:
        result = ImageChops.lighter(result, mask)
    return result


def paint_rect(mask: Image.Image, box: tuple[int, int, int, int]) -> None:
    ImageDraw.Draw(mask).rectangle(box, fill=255)


def expand_box(box: tuple[int, int, int, int], padding_x: int, padding_y: int, size: tuple[int, int]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    return (
        max(0, x0 - padding_x),
        max(0, y0 - padding_y),
        min(size[0], x1 + padding_x),
        min(size[1], y1 + padding_y),
    )


def transformed_layer(source: Image.Image, mask: Image.Image, bbox: tuple[int, int, int, int]) -> Image.Image:
    crop = source.crop(bbox).convert("RGBA")
    # Every heuristic mask is computed from a rectangular region. Intersect it
    # with the keyed foreground so a feature can never bring the magenta
    # generation background into the exported layer.
    effective_mask = ImageChops.multiply(mask, foreground_mask(source))
    crop.putalpha(effective_mask.crop(bbox))
    scale = TARGET_HEIGHT / (bbox[3] - bbox[1])
    width = max(1, round((bbox[2] - bbox[0]) * scale))
    crop = crop.resize((width, TARGET_HEIGHT), Image.Resampling.LANCZOS)
    # Resampling can blend a one-pixel magenta fringe back into otherwise
    # transparent edges. Remove that fringe after scaling as well.
    pixels = crop.load()
    for y in range(crop.height):
        for x in range(crop.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha and is_magenta(red, green, blue):
                pixels[x, y] = (red, green, blue, 0)
    canvas = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    canvas.alpha_composite(crop, ((CELL_SIZE - width) // 2, BASELINE_Y - TARGET_HEIGHT))
    return canvas


def split_cell(cell: Image.Image, direction: str) -> tuple[tuple[int, int, int, int], dict[str, Image.Image]]:
    foreground = foreground_mask(cell)
    bbox = foreground.getbbox()
    if bbox is None:
        raise ValueError("turnaround cell has no foreground")
    left, top, right, bottom = bbox
    head_bottom = top + round((bottom - top) * 0.45)
    head_region = (left, top, right, head_bottom)

    hair = color_mask(
        cell,
        lambda r, g, b: r < 125 and b > r + 12 and b > g + 15,
        head_region,
    )
    # The iris is the most stable landmark in this generated sheet. Restrict
    # the search to the lower part of the head; otherwise navy hair is
    # frequently classified as blue eye material.
    head_height = head_bottom - top
    eye_region = (
        left,
        top + round(head_height * 0.62),
        right,
        min(head_bottom, top + round(head_height * 0.98)),
    )
    blue = color_mask(
        cell,
        lambda r, g, b: b > 95 and b > r * 1.12 and b > g * 1.03 and r < 170,
        eye_region,
    )
    eye_box_mask = Image.new("L", cell.size, 0)
    eye_boxes: list[tuple[int, int, int, int]] = []
    if direction != "back":
        candidates = []
        for area, eye_box in component_boxes(blue, minimum=20):
            x0, y0, x1, y1 = eye_box
            center_y = (y0 + y1) / 2
            if area <= 900 and center_y >= top + head_height * 0.68:
                candidates.append((area, eye_box))
        # The front has two irises; each side has one. Keep the largest
        # landmarks and order them consistently from left to right.
        expected_eyes = 2 if direction == "front" else 1
        candidates = sorted(candidates, key=lambda item: item[0], reverse=True)[:expected_eyes]
        eye_boxes = sorted(
            [expand_box(box, 9, 13, cell.size) for _area, box in candidates],
            key=lambda box: box[0],
        )
        for eye_box in eye_boxes:
            paint_rect(eye_box_mask, eye_box)

    dark = color_mask(
        cell,
        lambda r, g, b: r < 105 and g < 105 and b < 145,
        head_region,
    )
    eyebrow = Image.new("L", cell.size, 0)
    if direction != "back":
        for eye_box in eye_boxes:
            x0, y0, x1, y1 = eye_box
            brow_box = (x0, max(top, y0 - 25), x1, min(head_bottom, y0 + 3))
            region = dark.crop(brow_box)
            # Hair overlaps the brow zone in this design, so retain only the
            # dark pixels not already classified as hair.
            region = ImageChops.multiply(region, ImageChops.invert(hair.crop(brow_box)))
            eyebrow.paste(region, (brow_box[0], brow_box[1]))

    skin = color_mask(
        cell,
        lambda r, g, b: r > 155 and g > 125 and b > 105 and r >= g - 8 and g >= b - 12,
        head_region,
    )
    # A warmer skin-tone mask is used to keep the pale eye whites while still
    # retaining the face in face_base. The generated eye whites are nearly
    # neutral, while the face has a visible warm tint.
    skin_tone = color_mask(
        cell,
        lambda r, g, b: r > 155 and g > 125 and b > 105 and r - g > 4 and g - b > 5,
        head_region,
    )
    eye_mask = ImageChops.multiply(eye_box_mask, foreground)
    eye_mask = ImageChops.multiply(eye_mask, ImageChops.invert(hair))
    eye_mask = ImageChops.multiply(eye_mask, ImageChops.invert(skin_tone))
    hair = ImageChops.multiply(hair, ImageChops.invert(eye_mask))
    ear = Image.new("L", cell.size, 0)
    ear_draw = ImageDraw.Draw(ear)
    ear_top = top + round(head_height * 0.45)
    ear_bottom = top + round(head_height * 0.92)
    ear_draw.rectangle((left, ear_top, left + round((right - left) * 0.22), ear_bottom), fill=255)
    ear_draw.rectangle((right - round((right - left) * 0.22), ear_top, right, ear_bottom), fill=255)
    ear = ImageChops.darker(skin, ear)

    feature_mask = union_masks(hair, eye_mask, eyebrow, ear)
    face_base = ImageChops.multiply(skin, ImageChops.invert(feature_mask))
    layers = {
        "full": transformed_layer(cell, foreground, bbox),
        "face_base": transformed_layer(cell, face_base, bbox),
        "eyes": transformed_layer(cell, eye_mask, bbox),
        "eyebrows": transformed_layer(cell, eyebrow, bbox),
        "ears": transformed_layer(cell, ear, bbox),
        "hair": transformed_layer(cell, hair, bbox),
    }
    return bbox, layers


def main() -> int:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image = Image.open(SOURCE).convert("RGB")
    layer_names = ("full", "face_base", "eyes", "eyebrows", "ears", "hair")
    for layer_name in layer_names:
        (OUTPUT / layer_name).mkdir(parents=True, exist_ok=True)

    manifest = {
        "generator": "process_turnaround_layers.py",
        "generator_version": 2,
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "design_reference": "front-character-anchor.png",
        "directions": DIRECTIONS,
        "cell_layout": "2x2_front_right_back_left",
        "canvas": [CELL_SIZE, CELL_SIZE],
        "baseline_y": BASELINE_Y,
        "layers": list(layer_names),
        "split_quality": "rough_reference_only",
        "randomization_ready": False,
        "directional_feature_policy": {
            "front": {"eyes": 2, "eyebrows": 2, "ears": 2},
            "right": {"eyes": 1, "eyebrows": 1, "ears": 1},
            "back": {"eyes": 0, "eyebrows": 0, "ears": 2},
            "left": {"eyes": 1, "eyebrows": 1, "ears": 1},
        },
        "notes": "Color and region heuristics are for alignment study; redraw masks before production randomization.",
        "frames": {},
    }
    for index, direction in enumerate(DIRECTIONS):
        row, column = divmod(index, COLUMNS)
        x0 = round(column * image.width / COLUMNS)
        x1 = round((column + 1) * image.width / COLUMNS)
        y0 = round(row * image.height / ROWS)
        y1 = round((row + 1) * image.height / ROWS)
        _bbox, layers = split_cell(image.crop((x0, y0, x1, y1)), direction)
        manifest["frames"][direction] = {}
        for layer_name, layer_image in layers.items():
            path = OUTPUT / layer_name / f"{direction}.png"
            layer_image.save(path)
            manifest["frames"][direction][layer_name] = path.relative_to(ROOT).as_posix()

    (OUTPUT / "turnaround_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("TURNAROUND_LAYER_PROCESS_PASS directions=4 layers=6 quality=rough_reference_only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
