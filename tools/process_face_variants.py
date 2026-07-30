from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "prototype" / "assets" / "characters" / "generated" / "raw_face_overlay_variants_2x4.png"
EAR_SOURCE = ROOT / "prototype" / "assets" / "characters" / "generated" / "raw_ear_overlay_variants_2x4.png"
OUTPUT = ROOT / "prototype" / "assets" / "characters" / "faces"
CELL_SIZE = 64
COLUMNS = 4
ROWS = 2
VARIANT_COUNT = COLUMNS * ROWS
DIRECTIONS = ["front", "right", "back", "left"]
FRAME_COUNT = 8

VARIANT_FACTORS = [
    {"eye_shape": "gentle_oval", "blush": False},
    {"eye_shape": "round", "blush": True},
    {"eye_shape": "narrow_confident", "blush": False},
    {"eye_shape": "sleepy", "blush": True},
    {"eye_shape": "large_sparkle", "blush": False},
    {"eye_shape": "determined", "blush": True},
    {"eye_shape": "dot", "blush": False},
    {"eye_shape": "cheerful_curve", "blush": True},
]
EAR_FACTORS = [
    "small_round",
    "large_round",
    "subtle_elf",
    "long_elf",
    "pointed_earring",
    "round_earring",
    "angular_fantasy",
    "soft_round_accent",
]


def frame_bounds(source: Image.Image, row: int, column: int) -> tuple[int, int, int, int]:
    x0 = round(column * source.width / COLUMNS)
    x1 = round((column + 1) * source.width / COLUMNS)
    y0 = round(row * source.height / ROWS)
    y1 = round((row + 1) * source.height / ROWS)
    return x0, y0, x1, y1


def chroma_key(cell: Image.Image) -> Image.Image:
    rgba = cell.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, _ = pixels[x, y]
            magenta_energy = red + blue - 2 * green
            is_background = (
                red > 170
                and blue > 95
                and green < 95
                and magenta_energy > 210
            )
            if is_background:
                pixels[x, y] = (0, 0, 0, 0)
            else:
                pixels[x, y] = (red, green, blue, 255)
    return rgba


def fit_overlay(cell: Image.Image) -> Image.Image:
    keyed = chroma_key(cell)
    bbox = keyed.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("face cell has no non-background pixels")

    # Keep the generated relative spacing, but normalize the feature group to
    # the same 64x64 registration used by the character head layers.
    cropped = keyed.crop(bbox)
    scale = min(1.0, 48.0 / max(cropped.width, cropped.height))
    resized = cropped.resize(
        (
            max(1, round(cropped.width * scale)),
            max(1, round(cropped.height * scale)),
        ),
        Image.Resampling.LANCZOS,
    )
    resized_pixels = resized.load()
    for y in range(resized.height):
        for x in range(resized.width):
            red, green, blue, alpha = resized_pixels[x, y]
            magenta_energy = red + blue - 2 * green
            if alpha < 64 or (red > 170 and blue > 95 and green < 110 and magenta_energy > 190):
                resized_pixels[x, y] = (0, 0, 0, 0)
    canvas = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    x = (CELL_SIZE - resized.width) // 2
    # The head face area is slightly above the cell center.
    y = 22 - resized.height // 2
    canvas.alpha_composite(resized, (x, y))
    return canvas


def process_overlay_sheet(source: Image.Image, variant_id: int) -> Image.Image:
    row = variant_id // COLUMNS
    column = variant_id % COLUMNS
    return fit_overlay(source.crop(frame_bounds(source, row, column)))


def empty_frame() -> Image.Image:
    return Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    if not EAR_SOURCE.exists():
        raise FileNotFoundError(EAR_SOURCE)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE).convert("RGB")
    ear_source = Image.open(EAR_SOURCE).convert("RGB")
    variants: list[dict[str, object]] = []

    for variant_id in range(VARIANT_COUNT):
        row = variant_id // COLUMNS
        column = variant_id % COLUMNS
        overlay = process_overlay_sheet(source, variant_id)
        ear_overlay = process_overlay_sheet(ear_source, variant_id)
        variant_root = OUTPUT / f"face_{variant_id:02d}"
        frame_root = variant_root / "frames"
        frame_root.mkdir(parents=True, exist_ok=True)
        ear_root = OUTPUT / f"ear_{variant_id:02d}"
        ear_frame_root = ear_root / "frames"
        ear_frame_root.mkdir(parents=True, exist_ok=True)
        atlas = Image.new("RGBA", (COLUMNS * CELL_SIZE, len(DIRECTIONS) * CELL_SIZE), (0, 0, 0, 0))
        ear_atlas = Image.new("RGBA", (COLUMNS * CELL_SIZE, len(DIRECTIONS) * CELL_SIZE), (0, 0, 0, 0))

        frame_names: list[list[str]] = []
        for direction_row, _direction in enumerate(DIRECTIONS):
            row_names: list[str] = []
            for frame in range(FRAME_COUNT):
                image = overlay if direction_row == 0 else empty_frame()
                ear_image = ear_overlay if direction_row == 0 else empty_frame()
                name = f"walk_row{direction_row}_frame{frame}.png"
                image.save(frame_root / name)
                ear_image.save(ear_frame_root / name)
                atlas.alpha_composite(image, (frame * CELL_SIZE, direction_row * CELL_SIZE))
                ear_atlas.alpha_composite(ear_image, (frame * CELL_SIZE, direction_row * CELL_SIZE))
                row_names.append(name)
            frame_names.append(row_names)
        atlas.save(variant_root / "face_walk_4way.png")
        ear_atlas.save(ear_root / "ear_walk_4way.png")
        variants.append(
            {
                "id": variant_id,
                "path": f"face_{variant_id:02d}",
                "ear_path": f"ear_{variant_id:02d}",
                "source_cell": {"row": row, "column": column},
                "factors": VARIANT_FACTORS[variant_id],
                "ear_factor": EAR_FACTORS[variant_id],
                "front_only": True,
                "frames": frame_names,
            }
        )

    manifest = {
        "generator": "process_face_variants.py",
        "generator_version": 1,
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "ear_source": EAR_SOURCE.relative_to(ROOT).as_posix(),
        "cell_size": [CELL_SIZE, CELL_SIZE],
        "columns": FRAME_COUNT,
        "rows": len(DIRECTIONS),
        "directions": DIRECTIONS,
        "frame_count_per_direction": FRAME_COUNT,
        "variant_count": VARIANT_COUNT,
        "selection": "stable appearance_seed selects one face variant",
        "gender_rules": {
            "male": {"allowed_variants": [0, 2, 4, 6], "blush": False},
            "female": {"allowed_variants": [0, 1, 2, 3, 4, 5, 6, 7], "blush": "optional"},
        },
        "components": ["ears", "eyes", "optional_blush"],
        "forbidden_components": ["nose", "mouth"],
        "front_only": True,
        "variants": variants,
    }
    (OUTPUT / "face_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"FACE_VARIANT_PROCESS_PASS variants={VARIANT_COUNT} frames={VARIANT_COUNT * 32}")


if __name__ == "__main__":
    main()
