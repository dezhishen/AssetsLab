"""Build a normalized review asset for the corrected recommended side walk base."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "prototype/assets/characters/generated/recommended_base_horizontal_layer_fix_v1/right_source.png"
OUTPUT = SOURCE.parent / "runtime"
FRAME_COUNT = 8
CELL_SIZE = (64, 64)
TARGET_HEIGHT = 50
BASELINE = 60


def subject_mask(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    raw = Image.new("L", rgb.size, 0)
    source = rgb.load()
    pixels = raw.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            red, green, blue = source[x, y]
            brightness = (red + green + blue) / 3.0
            # The source background is neutral gray/white; the mannequin is warm.
            if red - blue >= 7 and brightness >= 105:
                pixels[x, y] = 255

    expanded = raw.filter(ImageFilter.MaxFilter(9))
    output = Image.new("L", rgb.size, 0)
    expanded_pixels = expanded.load()
    output_pixels = output.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            red, green, blue = source[x, y]
            brightness = (red + green + blue) / 3.0
            if pixels[x, y] or (expanded_pixels[x, y] and brightness < 175):
                output_pixels[x, y] = 255
    return output


def split_columns(mask: Image.Image) -> list[tuple[int, int]]:
    columns = [any(mask.getpixel((x, y)) for y in range(mask.height)) for x in range(mask.width)]
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    for index, occupied in enumerate(columns + [False]):
        if occupied and start is None:
            start = index
        elif not occupied and start is not None:
            ranges.append((start, index - 1))
            start = None

    merged: list[tuple[int, int]] = []
    for left, right in ranges:
        if merged and left - merged[-1][1] <= 3:
            merged[-1] = (merged[-1][0], right)
        else:
            merged.append((left, right))
    if len(merged) != FRAME_COUNT:
        raise ValueError(f"expected {FRAME_COUNT} source subjects, found {len(merged)}: {merged}")
    return merged


def normalize_frame(source: Image.Image, mask: Image.Image, column_range: tuple[int, int]) -> Image.Image:
    left, right = column_range
    local_mask = mask.crop((left, 0, right + 1, mask.height))
    bbox = local_mask.getbbox()
    if bbox is None:
        raise ValueError("source frame has no subject")
    # Include the full local height and use the subject bbox only for scaling.
    crop = source.crop((left, bbox[1], right + 1, bbox[3]))
    crop_mask = local_mask.crop((0, bbox[1], local_mask.width, bbox[3]))
    alpha_bbox = crop_mask.getbbox()
    assert alpha_bbox is not None
    subject_height = alpha_bbox[3] - alpha_bbox[1]
    scale = TARGET_HEIGHT / subject_height
    scaled_size = (max(1, round(crop.width * scale)), TARGET_HEIGHT)
    scaled = crop.resize(scaled_size, Image.Resampling.LANCZOS)
    scaled_mask = crop_mask.resize(scaled_size, Image.Resampling.NEAREST)
    scaled.putalpha(scaled_mask)

    output = Image.new("RGBA", CELL_SIZE, (0, 0, 0, 0))
    x = (CELL_SIZE[0] - scaled.width) // 2
    y = BASELINE - scaled.height
    output.alpha_composite(scaled, (x, y))
    return output


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE).convert("RGBA")
    mask = subject_mask(source)
    ranges = split_columns(mask)
    frames: list[Image.Image] = []
    for index, column_range in enumerate(ranges):
        frame = normalize_frame(source, mask, column_range)
        frames.append(frame)
        frame.save(OUTPUT / f"right_frame{index}.png")

    sheet = Image.new("RGBA", (CELL_SIZE[0] * FRAME_COUNT, CELL_SIZE[1]), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        sheet.alpha_composite(frame, (index * CELL_SIZE[0], 0))
    sheet.save(OUTPUT / "right_walk_8.png")
    frames[0].save(OUTPUT / "right_walk_8.gif", save_all=True, append_images=frames[1:], duration=120, loop=0, disposal=2)

    manifest = {
        "schema": "recommended_horizontal_layer_fix_v1",
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "direction": "right",
        "cell_size": list(CELL_SIZE),
        "frames": FRAME_COUNT,
        "frame_order": ["contact_a", "down_a", "passing_a", "up_a", "contact_b", "down_b", "passing_b", "up_b"],
        "foot_occlusion_policy": ["right_front", "right_front", "right_front", "left_front", "left_front", "left_front", "left_front", "right_front"],
        "runtime_frames": [f"right_frame{index}.png" for index in range(FRAME_COUNT)],
        "notes": "Review candidate generated from the recommended base. The front leg switches after frame 3 and returns after frame 7; this is not the older redraw adapter.",
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"RECOMMENDED_HORIZONTAL_FIX_PASS frames={FRAME_COUNT} output={OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
