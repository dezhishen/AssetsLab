from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "prototype" / "assets" / "characters" / "generated" / "body_base_rebuild_v2_male.png"
OUTPUT = ROOT / "prototype" / "assets" / "characters" / "rebuild_body_v2"
PREVIEW = ROOT / "prototype" / "preview" / "assets"
DIRECTIONS = ("front", "right", "back", "left")
PANEL_BBOXES = (
    (145, 127, 547, 596),
    (747, 127, 940, 596),
    (1140, 127, 1541, 596),
    (1715, 127, 1907, 596),
)
CELL_SIZE = 64
FRAMES_PER_DIRECTION = 8
TARGET_BODY_HEIGHT = 29
BASELINE_Y = 58
WALK_OFFSETS = (0, -1, -2, -2, 0, 1, 2, 2)


def alpha_mask(image: Image.Image) -> Image.Image:
    return image.getchannel("A").point(lambda value: 255 if value >= 32 else 0)


def restrict(mask: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    region = Image.new("L", mask.size, 0)
    ImageDraw.Draw(region).rectangle(box, fill=255)
    return ImageChops.multiply(mask, region)


def fit_body(panel: Image.Image) -> Image.Image:
    mask = alpha_mask(panel)
    bbox = mask.getbbox()
    if bbox is None:
        raise ValueError("empty generated body panel")
    crop = panel.crop(bbox).convert("RGBA")
    crop.putalpha(mask.crop(bbox))
    scale = TARGET_BODY_HEIGHT / crop.height
    width = max(1, round(crop.width * scale))
    crop = crop.resize((width, TARGET_BODY_HEIGHT), Image.Resampling.LANCZOS)
    pixels = crop.load()
    for y in range(crop.height):
        for x in range(crop.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha < 32:
                pixels[x, y] = (red, green, blue, 0)
    result = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    result.alpha_composite(crop, ((CELL_SIZE - width) // 2, BASELINE_Y - TARGET_BODY_HEIGHT))
    return result


def shift_same_size(image: Image.Image, dx: int, dy: int = 0) -> Image.Image:
    shifted = Image.new("RGBA", image.size, (0, 0, 0, 0))
    source_box = (
        max(0, -dx),
        max(0, -dy),
        min(image.width, image.width - dx),
        min(image.height, image.height - dy),
    )
    target = (max(0, dx), max(0, dy))
    if source_box[2] > source_box[0] and source_box[3] > source_box[1]:
        shifted.alpha_composite(image.crop(source_box), target)
    return shifted


def shift_half(image: Image.Image, left_dx: int, right_dx: int, start_y: int = 0) -> Image.Image:
    midpoint = image.width // 2
    left_mask = Image.new("L", image.size, 0)
    right_mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(left_mask).rectangle((0, 0, midpoint - 1, image.height - 1), fill=255)
    ImageDraw.Draw(right_mask).rectangle((midpoint, 0, image.width - 1, image.height - 1), fill=255)
    if start_y > 0:
        y_mask = Image.new("L", image.size, 0)
        ImageDraw.Draw(y_mask).rectangle((0, start_y, image.width - 1, image.height - 1), fill=255)
        left_mask = ImageChops.multiply(left_mask, y_mask)
        right_mask = ImageChops.multiply(right_mask, y_mask)
    left = Image.new("RGBA", image.size, (0, 0, 0, 0))
    right = Image.new("RGBA", image.size, (0, 0, 0, 0))
    left_alpha = ImageChops.multiply(image.getchannel("A"), left_mask)
    right_alpha = ImageChops.multiply(image.getchannel("A"), right_mask)
    left.paste(image, (0, 0), left_alpha)
    right.paste(image, (0, 0), right_alpha)
    static = image.copy()
    static.putalpha(ImageChops.subtract(image.getchannel("A"), ImageChops.lighter(left_alpha, right_alpha)))
    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    result.alpha_composite(static)
    result.alpha_composite(shift_same_size(left, left_dx))
    result.alpha_composite(shift_same_size(right, right_dx))
    return result


def shift_segment(image: Image.Image, start_y: int, dx: int) -> Image.Image:
    moving_mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(moving_mask).rectangle((0, start_y, image.width - 1, image.height - 1), fill=255)
    moving_alpha = ImageChops.multiply(image.getchannel("A"), moving_mask)
    moving = Image.new("RGBA", image.size, (0, 0, 0, 0))
    moving.paste(image, (0, 0), moving_alpha)
    static = image.copy()
    static.putalpha(ImageChops.subtract(image.getchannel("A"), moving_alpha))
    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    result.alpha_composite(static)
    result.alpha_composite(shift_same_size(moving, dx))
    return result


def animated_layer(image: Image.Image, direction: str, layer: str, frame: int) -> Image.Image:
    """Add compact alternating motion while keeping the generated torso fixed."""
    offset = WALK_OFFSETS[frame]
    if layer == "lower_body":
        if direction in {"front", "back"}:
            # Move the two visible legs in opposite phases rather than
            # translating the whole lower body as one rigid block.
            return shift_half(image, offset, -offset, 48)
        return shift_segment(image, 48, offset)
    if layer == "feet":
        if direction in {"front", "back"}:
            return shift_half(image, offset, -offset, 53)
        return shift_segment(image, 53, round(offset * 1.5))
    return image


def split_layers(body: Image.Image) -> dict[str, Image.Image]:
    mask = alpha_mask(body)
    layers: dict[str, Image.Image] = {}
    regions = {
        "torso": (0, 0, CELL_SIZE - 1, 47),
        "arms": (0, 35, CELL_SIZE - 1, 55),
        "lower_body": (0, 44, CELL_SIZE - 1, CELL_SIZE - 1),
        "feet": (0, 53, CELL_SIZE - 1, CELL_SIZE - 1),
    }
    for layer, region in regions.items():
        part = Image.new("RGBA", body.size, (0, 0, 0, 0))
        part.putalpha(restrict(mask, region))
        body_rgb = body.convert("RGB")
        part.paste(body_rgb, (0, 0), part.getchannel("A"))
        layers[layer] = part
    layers["body_base"] = body
    return layers


def main() -> int:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    source = Image.open(SOURCE).convert("RGBA")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    processed: dict[str, dict[str, Image.Image]] = {}
    manifest = {
        "generator": "process_rebuild_body.py",
        "generator_version": 1,
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "directions": list(DIRECTIONS),
        "cell_size": [CELL_SIZE, CELL_SIZE],
        "frames_per_direction": FRAMES_PER_DIRECTION,
        "target_body_height": TARGET_BODY_HEIGHT,
        "baseline_y": BASELINE_Y,
        "status": "procedural_compact_walk_reference",
        "walk_offsets": list(WALK_OFFSETS),
        "layer_order": ["feet", "lower_body", "arms", "torso", "body_base"],
        "frames": {},
    }
    for direction, panel_bbox in zip(DIRECTIONS, PANEL_BBOXES):
        body = fit_body(source.crop(panel_bbox))
        layers = split_layers(body)
        processed[direction] = layers
        manifest["frames"][direction] = {}
        for layer, image in layers.items():
            layer_dir = OUTPUT / layer
            layer_dir.mkdir(parents=True, exist_ok=True)
            sheet = Image.new("RGBA", (CELL_SIZE * FRAMES_PER_DIRECTION, CELL_SIZE), (0, 0, 0, 0))
            for frame in range(FRAMES_PER_DIRECTION):
                animated = image if layer == "body_base" else animated_layer(image, direction, layer, frame)
                path = layer_dir / f"{direction}_frame{frame}.png"
                animated.save(path)
                sheet.alpha_composite(animated, (frame * CELL_SIZE, 0))
            sheet_path = layer_dir / f"{direction}_walk_8.png"
            sheet.save(sheet_path)
            manifest["frames"][direction][layer] = {
                "sheet": sheet_path.relative_to(ROOT).as_posix(),
                "frame_directory": layer_dir.relative_to(ROOT).as_posix(),
            }

        preview = layers["body_base"].resize((512, 512), Image.Resampling.NEAREST)
        ImageDraw.Draw(preview).text((16, 16), f"new body {direction}", fill=(242, 241, 238, 255), font=ImageFont.load_default())
        preview.save(PREVIEW / f"rebuild_body_candidate_{direction}.png")

    # Also expose the new body in the same 4x8 sheet interface consumed by
    # the preview/Godot runtime builders.
    for layer in ("torso", "arms", "lower_body", "feet"):
        sheet = Image.new("RGBA", (CELL_SIZE * FRAMES_PER_DIRECTION, CELL_SIZE * len(DIRECTIONS)), (0, 0, 0, 0))
        for row, direction in enumerate(DIRECTIONS):
            for frame in range(FRAMES_PER_DIRECTION):
                image = Image.open(OUTPUT / layer / f"{direction}_frame{frame}.png").convert("RGBA")
                sheet.alpha_composite(image, (frame * CELL_SIZE, row * CELL_SIZE))
        sheet.save(OUTPUT / f"{layer}_walk_4way.png")

    (OUTPUT / "rebuild_body_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("REBUILD_BODY_PROCESS_PASS directions=4 layers=5 frames=32 status=procedural_compact_walk_reference source=v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
