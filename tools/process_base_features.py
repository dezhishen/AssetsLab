from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CHARACTER_ROOT = ROOT / "prototype" / "assets" / "characters"
FACE_SOURCE = CHARACTER_ROOT / "generated" / "raw_face_base_v1_4x4.png"
EAR_SOURCE = CHARACTER_ROOT / "generated" / "raw_ear_base_v1_4x4.png"
OUTPUT = CHARACTER_ROOT / "base_features_v1"
ROWS = 4
SOURCE_COLUMNS = 4
OUTPUT_COLUMNS = 8
CELL_SIZE = 64
DIRECTIONS = ["front", "right", "back", "left"]
HEAD_VARIANTS = ["male", "female"]


def frame_bounds(source: Image.Image, row: int, column: int) -> tuple[int, int, int, int]:
    return (
        round(column * source.width / SOURCE_COLUMNS),
        round(row * source.height / ROWS),
        round((column + 1) * source.width / SOURCE_COLUMNS),
        round((row + 1) * source.height / ROWS),
    )


def chroma_key(image: Image.Image) -> Image.Image:
    result = image.convert("RGBA")
    pixels = result.load()
    for y in range(result.height):
        for x in range(result.width):
            red, green, blue, _alpha = pixels[x, y]
            energy = red + blue - 2 * green
            if red > 170 and blue > 95 and green < 110 and energy > 190:
                pixels[x, y] = (0, 0, 0, 0)
            else:
                pixels[x, y] = (red, green, blue, 255)
    return result


def remove_blush(image: Image.Image) -> Image.Image:
    result = image.copy()
    pixels = result.load()
    for y in range(result.height):
        for x in range(result.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha > 0 and red > 150 and green > 100 and blue > 80:
                pixels[x, y] = (0, 0, 0, 0)
    return result


def fit_to_anchor(
    source_cell: Image.Image,
    target_width: int,
    target_height: int,
    center: tuple[float, float],
    male: bool = False,
) -> Image.Image:
    keyed = chroma_key(source_cell)
    if male:
        keyed = remove_blush(keyed)
    bbox = keyed.getchannel("A").getbbox()
    if bbox is None:
        return Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    cropped = keyed.crop(bbox)
    scale = min(target_width / cropped.width, target_height / cropped.height, 1.0)
    resized = cropped.resize(
        (max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale))),
        Image.Resampling.LANCZOS,
    )
    pixels = resized.load()
    for y in range(resized.height):
        for x in range(resized.width):
            red, green, blue, alpha = pixels[x, y]
            energy = red + blue - 2 * green
            if alpha < 48 or (red > 170 and blue > 95 and green < 110 and energy > 190):
                pixels[x, y] = (0, 0, 0, 0)
    canvas = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    x = round(center[0] - resized.width / 2)
    y = round(center[1] - resized.height / 2)
    canvas.alpha_composite(resized, (x, y))
    return canvas


def head_bbox(gender: str, row: int, frame: int) -> tuple[int, int, int, int]:
    path = CHARACTER_ROOT / "chibi" / f"head_{gender}_frames" / f"walk_row{row}_frame{frame}.png"
    with Image.open(path) as image:
        bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"empty head frame: {path}")
    return bbox


def feature_anchor(layer: str, row: int, bbox: tuple[int, int, int, int]) -> tuple[tuple[float, float], tuple[int, int]] | None:
    left, top, right, bottom = bbox
    center_x = (left + right - 1) / 2
    face_y = top + 15
    if layer == "face":
        if row == 2:
            return None
        if row == 0:
            return (center_x, face_y), (20, 10)
        if row == 1:
            return (right - 6, face_y), (8, 11)
        return (left + 6, face_y), (8, 11)
    if row in (0, 2):
        return (center_x, face_y), (34, 14)
    if row == 1:
        return (left + 3, face_y), (9, 13)
    return (right - 3, face_y), (9, 13)


def process_layer(source: Image.Image, gender: str, layer: str) -> list[list[str]]:
    output_root = OUTPUT / gender / f"{layer}_frames"
    output_root.mkdir(parents=True, exist_ok=True)
    atlas = Image.new("RGBA", (OUTPUT_COLUMNS * CELL_SIZE, ROWS * CELL_SIZE), (0, 0, 0, 0))
    names: list[list[str]] = []
    male = gender == "male" and layer == "face"
    for row in range(ROWS):
        row_names: list[str] = []
        for frame in range(OUTPUT_COLUMNS):
            source_column = frame % SOURCE_COLUMNS
            anchor = feature_anchor(layer, row, head_bbox(gender, row, frame))
            if anchor is None:
                image = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
            else:
                source_cell = source.crop(frame_bounds(source, row, source_column))
                image = fit_to_anchor(source_cell, *anchor[1], anchor[0], male=male)
            name = f"walk_row{row}_frame{frame}.png"
            image.save(output_root / name)
            atlas.alpha_composite(image, (frame * CELL_SIZE, row * CELL_SIZE))
            row_names.append(name)
        names.append(row_names)
    atlas.save(OUTPUT / gender / f"{layer}_walk_4way.png")
    return names


def main() -> int:
    for path in (FACE_SOURCE, EAR_SOURCE):
        if not path.exists():
            raise FileNotFoundError(path)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    face_source = Image.open(FACE_SOURCE).convert("RGB")
    ear_source = Image.open(EAR_SOURCE).convert("RGB")
    manifest = {
        "generator": "process_base_features.py",
        "generator_version": 1,
        "sources": {
            "face": FACE_SOURCE.relative_to(ROOT).as_posix(),
            "ear": EAR_SOURCE.relative_to(ROOT).as_posix(),
        },
        "cell_size": [CELL_SIZE, CELL_SIZE],
        "directions": DIRECTIONS,
        "frame_count_per_direction": OUTPUT_COLUMNS,
        "layers": ["ear", "face"],
        "head_registration": "per_gender_per_direction_per_frame_alpha_bbox",
        "face_limits": {"front": [20, 10], "side": [8, 11], "back": [0, 0]},
        "ear_limits": {"front_back": [34, 14], "side": [9, 13]},
        "no_nose": True,
        "no_mouth": True,
        "randomization_ready": False,
        "frame_names": {},
    }
    for gender in HEAD_VARIANTS:
        manifest["frame_names"][gender] = {
            "face": process_layer(face_source, gender, "face"),
            "ear": process_layer(ear_source, gender, "ear"),
        }
    (OUTPUT / "base_features_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print("BASE_FEATURE_PROCESS_PASS genders=2 layers=4 frames=64")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
