from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "prototype" / "assets" / "characters" / "generated" / "character_head_rebuild_v1_male.png"
OUTPUT = ROOT / "prototype" / "assets" / "characters" / "rebuilt_head_v1"
DIRECTIONS = ("front", "right", "back", "left")
CELL_SIZE = 256
SOURCE_COLUMNS = 2
SOURCE_ROWS = 2
TARGET_HEIGHT = 220
BASELINE_Y = 238


def is_magenta(red: int, green: int, blue: int) -> bool:
    return red > 150 and blue > 120 and green < 105 and red + blue - 2 * green > 200


def alpha_mask(image: Image.Image) -> Image.Image:
    return image.getchannel("A").point(lambda value: 255 if value >= 16 else 0)


def color_mask(image: Image.Image, predicate, region: tuple[int, int, int, int]) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    pixels = image.load()
    target = mask.load()
    x0, y0, x1, y1 = region
    for y in range(max(0, y0), min(image.height, y1)):
        for x in range(max(0, x0), min(image.width, x1)):
            red, green, blue, alpha = pixels[x, y]
            if alpha >= 16 and predicate(red, green, blue):
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


def expand_box(box: tuple[int, int, int, int], pad_x: int, pad_y: int, size: tuple[int, int]) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    return max(0, x0 - pad_x), max(0, y0 - pad_y), min(size[0], x1 + pad_x), min(size[1], y1 + pad_y)


def union_masks(*masks: Image.Image) -> Image.Image:
    result = Image.new("L", masks[0].size, 0)
    for mask in masks:
        result = ImageChops.lighter(result, mask)
    return result


def restricted(mask: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    region = Image.new("L", mask.size, 0)
    ImageDraw.Draw(region).rectangle(box, fill=255)
    return ImageChops.multiply(mask, region)


def paint_boxes(size: tuple[int, int], boxes: list[tuple[int, int, int, int]]) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for box in boxes:
        draw.rectangle(box, fill=255)
    return mask


def transformed_layer(source: Image.Image, mask: Image.Image, bbox: tuple[int, int, int, int]) -> Image.Image:
    crop = source.crop(bbox).convert("RGBA")
    crop.putalpha(ImageChops.multiply(mask, alpha_mask(source)).crop(bbox))
    scale = TARGET_HEIGHT / (bbox[3] - bbox[1])
    width = max(1, round((bbox[2] - bbox[0]) * scale))
    crop = crop.resize((width, TARGET_HEIGHT), Image.Resampling.LANCZOS)
    pixels = crop.load()
    for y in range(crop.height):
        for x in range(crop.width):
            red, green, blue, opacity = pixels[x, y]
            if opacity and is_magenta(red, green, blue):
                pixels[x, y] = (red, green, blue, 0)
    canvas = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    canvas.alpha_composite(crop, ((CELL_SIZE - width) // 2, BASELINE_Y - TARGET_HEIGHT))
    return canvas


def split_head(cell: Image.Image, direction: str) -> tuple[tuple[int, int, int, int], dict[str, Image.Image]]:
    foreground = alpha_mask(cell)
    bbox = foreground.getbbox()
    if bbox is None:
        raise ValueError(f"empty head cell: {direction}")
    left, top, right, bottom = bbox
    head_height = bottom - top
    head_region = (left, top, right, bottom)

    hair = color_mask(
        cell,
        lambda r, g, b: r < 145 and b > r + 10 and b >= g - 2,
        head_region,
    )
    skin = color_mask(
        cell,
        lambda r, g, b: r > 150 and g > 100 and b > 80 and r > g + 5 and g > b + 5,
        head_region,
    )

    white = color_mask(
        cell,
        lambda r, g, b: r > 235 and g > 235 and b > 225,
        (left, top + round(head_height * 0.45), right, bottom),
    )
    eye_candidates = [
        (area, box)
        for area, box in component_boxes(white, minimum=300)
        if area >= 400
    ]
    expected_eyes = 2 if direction == "front" else 1 if direction in ("right", "left") else 0
    eye_candidates = sorted(eye_candidates, key=lambda item: item[0], reverse=True)[:expected_eyes]
    eye_boxes = sorted(
        [expand_box(box, 24, 18, cell.size) for _area, box in eye_candidates],
        key=lambda box: box[0],
    )
    eye_box_mask = paint_boxes(cell.size, eye_boxes)

    eye_mask = ImageChops.multiply(eye_box_mask, foreground)
    eye_mask = ImageChops.multiply(eye_mask, ImageChops.invert(skin))

    dark = color_mask(
        cell,
        lambda r, g, b: r < 100 and g < 100 and b < 125,
        head_region,
    )
    blue = color_mask(
        cell,
        lambda r, g, b: b > 95 and b > r * 1.12 and b > g * 1.03 and r < 170,
        head_region,
    )
    eye_detail = ImageChops.multiply(union_masks(white, dark, blue), eye_box_mask)
    eye_mask = ImageChops.multiply(eye_detail, foreground)
    eye_mask = ImageChops.multiply(eye_mask, ImageChops.invert(skin))
    eyebrow = Image.new("L", cell.size, 0)
    for x0, y0, x1, y1 in eye_boxes:
        brow_box = (x0, max(top, y0 - 30), x1, min(bottom, y0 + 3))
        brow = restricted(dark, brow_box)
        brow = ImageChops.multiply(brow, ImageChops.invert(hair))
        eyebrow = union_masks(eyebrow, brow)

    if direction == "front":
        ear_regions = [
            (left, top + round(head_height * 0.72), left + round((right - left) * 0.28), bottom),
            (right - round((right - left) * 0.28), top + round(head_height * 0.72), right, bottom),
        ]
        ear_ellipses = []
    elif direction == "right":
        ear_regions = []
        ear_ellipses = [(245, 420, 335, 505)]
    elif direction == "left":
        ear_regions = []
        ear_ellipses = [(285, 300, 380, 405)]
    else:
        ear_regions = [
            (left, top + round(head_height * 0.72), left + round((right - left) * 0.28), bottom),
            (right - round((right - left) * 0.28), top + round(head_height * 0.72), right, bottom),
        ]
        ear_ellipses = []
    ear = Image.new("L", cell.size, 0)
    if ear_ellipses:
        draw = ImageDraw.Draw(ear)
        for ellipse in ear_ellipses:
            draw.ellipse(ellipse, fill=255)
        ear = ImageChops.multiply(skin, ear)
    for region in ear_regions:
        ear = union_masks(ear, restricted(skin, region))

    hair = ImageChops.multiply(hair, ImageChops.invert(eye_mask))
    face_base = ImageChops.multiply(skin, ImageChops.invert(union_masks(eye_mask, eyebrow, ear)))
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
    image = Image.open(SOURCE).convert("RGBA")
    layer_names = ("full", "face_base", "eyes", "eyebrows", "ears", "hair")
    for layer_name in layer_names:
        (OUTPUT / layer_name).mkdir(parents=True, exist_ok=True)

    manifest = {
        "generator": "process_head_rebuild.py",
        "generator_version": 1,
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "design_reference": "front-character-anchor.png",
        "directions": list(DIRECTIONS),
        "cell_layout": "2x2_front_right_back_left",
        "canvas": [CELL_SIZE, CELL_SIZE],
        "baseline_y": BASELINE_Y,
        "layers": list(layer_names),
        "reconstruction_status": "component_rebuild_reference",
        "randomization_ready": False,
        "directional_feature_policy": {
            "front": {"eyes": 2, "eyebrows": 2, "ears": 2},
            "right": {"eyes": 1, "eyebrows": 1, "ears": 1},
            "back": {"eyes": 0, "eyebrows": 0, "ears": 2},
            "left": {"eyes": 1, "eyebrows": 1, "ears": 1},
        },
        "notes": "Components are reconstructed from a clean head-only reference. Manual redraw is still required before random variants.",
        "frames": {},
    }
    for index, direction in enumerate(DIRECTIONS):
        row, column = divmod(index, SOURCE_COLUMNS)
        x0 = round(column * image.width / SOURCE_COLUMNS)
        x1 = round((column + 1) * image.width / SOURCE_COLUMNS)
        y0 = round(row * image.height / SOURCE_ROWS)
        y1 = round((row + 1) * image.height / SOURCE_ROWS)
        _bbox, layers = split_head(image.crop((x0, y0, x1, y1)), direction)
        manifest["frames"][direction] = {}
        for layer_name, layer_image in layers.items():
            path = OUTPUT / layer_name / f"{direction}.png"
            layer_image.save(path)
            manifest["frames"][direction][layer_name] = path.relative_to(ROOT).as_posix()

    (OUTPUT / "rebuild_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("HEAD_REBUILD_PROCESS_PASS directions=4 layers=6 status=component_rebuild_reference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
