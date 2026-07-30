from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageOps


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
# The first pass placed features at head_top + 15.  That made the front-facing
# eyes and ears read too high and left too little room for future hair layers.
# Keep side views slightly tighter because their feature bounds are taller.
FEATURE_Y_OFFSETS = {"face": {0: 5, 1: 1, 2: 5, 3: 1}, "ear": {0: 5, 1: 4, 2: 5, 3: 4}}


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
    force_size: bool = False,
    symmetric_front: bool = False,
) -> Image.Image:
    keyed = chroma_key(source_cell)
    if male:
        keyed = remove_blush(keyed)
    bbox = keyed.getchannel("A").getbbox()
    if bbox is None:
        return Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    cropped = keyed.crop(bbox)
    if symmetric_front:
        half_width = max(1, cropped.width // 2)
        left_half = cropped.crop((0, 0, half_width, cropped.height))
        mirrored = ImageOps.mirror(left_half)
        symmetric = Image.new("RGBA", (half_width * 2, cropped.height), (0, 0, 0, 0))
        symmetric.alpha_composite(left_half, (0, 0))
        symmetric.alpha_composite(mirrored, (half_width, 0))
        cropped = symmetric
    if force_size:
        resized = cropped.resize((target_width, target_height), Image.Resampling.LANCZOS)
    else:
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
    feature_y = top + 15 + FEATURE_Y_OFFSETS[layer][row]
    if layer == "face":
        if row == 2:
            return None
        if row == 0:
            return (center_x, feature_y), (20, 8)
        if row == 1:
            return (right - 6, feature_y), (7, 9)
        return (left + 6, feature_y), (7, 9)
    if row in (0, 2):
        ear_width = 32 if row == 0 else 30
        return (center_x, feature_y), (ear_width, 12)
    if row == 1:
        # Right-facing profile: keep the ear inside the head so the rear
        # silhouette remains readable instead of turning the ear into the
        # apparent back edge.
        return (left + 10, feature_y), (8, 12)
    # Left-facing profile mirrors the same inset from the rear edge.
    return (right - 10, feature_y), (8, 12)


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
                image = fit_to_anchor(
                    source_cell,
                    *anchor[1],
                    anchor[0],
                    male=male,
                    force_size=layer == "face",
                    symmetric_front=layer == "face" and row == 0,
                )
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
        "generator_version": 6,
        "sources": {
            "face": FACE_SOURCE.relative_to(ROOT).as_posix(),
            "ear": EAR_SOURCE.relative_to(ROOT).as_posix(),
        },
        "cell_size": [CELL_SIZE, CELL_SIZE],
        "directions": DIRECTIONS,
        "frame_count_per_direction": OUTPUT_COLUMNS,
        "layers": ["ear", "face"],
        "head_registration": "per_gender_per_direction_per_frame_alpha_bbox",
        "feature_y_anchor": "head_top_plus_15_plus_layer_direction_offset",
        "face_scale_mode": "fixed_target_size_for_view_consistency",
        "front_face_layout": "mirrored_left_half_centered",
        "side_ear_layout": "inset_under_head_edge_with_ear_layer_above_head",
        "feature_y_offsets": {
            "face_front": 5,
            "face_side": 1,
            "face_back": 5,
            "ear_front": 5,
            "ear_side": 4,
            "ear_back": 5
        },
        "face_limits": {"front": [20, 8], "side": [7, 9], "back": [0, 0]},
        "ear_limits": {"front": [32, 12], "back": [30, 12], "side": [8, 12]},
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
