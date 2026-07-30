from __future__ import annotations

import json
import os
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "prototype" / "assets" / "characters" / "generated"
SHARED_SOURCE = GENERATED / "raw_qqtang_shared_bighead_walk_4x8.png"
MALE_HEAD_SOURCE = GENERATED / "raw_qqtang_male_head_big_walk_4x8.png"
FEMALE_HEAD_SOURCE = GENERATED / "raw_qqtang_female_head_big_walk_4x8.png"
OUTPUT = ROOT / "prototype" / "assets" / "characters" / "chibi"
ROWS = 4
COLUMNS = 8
CELL_SIZE = 64
TARGET_HEIGHT = 52
BASELINE_Y = 58
CENTER_X = CELL_SIZE // 2
HEAD_SPLIT_RATIO = 0.50
LOWER_BODY_SPLIT_RATIO = 0.66
SEAM_OVERLAP = 2
SIDE_LIMB_SCALE_X = 0.84
HEAD_REAR_EXPAND_X = 5


def is_chroma_fringe(red: int, green: int, blue: int) -> bool:
    """Detect both bright and dark magenta remnants from the source key."""
    return (
        red > 70
        and blue > 60
        and green < 135
        and red > green * 1.25
        and blue > green * 1.15
        and red + blue - 2 * green > 50
    )


def chroma_alpha(cell: Image.Image) -> Image.Image:
    """Remove generated magenta while preserving the neutral ivory mannequin."""
    rgb = cell.convert("RGB")
    alpha = Image.new("L", rgb.size, 0)
    source = rgb.load()
    target = alpha.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            red, green, blue = source[x, y]
            # The generated background has both bright and dark magenta pixels.
            # Use a color-distance rule instead of a single red threshold so
            # dark edge pixels cannot become stray foreground in one frame.
            if not is_chroma_fringe(red, green, blue):
                target[x, y] = 255
    return alpha


def remove_chroma_fringe(image: Image.Image) -> Image.Image:
    """Remove residual magenta pixels introduced by nearest-neighbour scaling."""
    result = image.copy().convert("RGBA")
    pixels = result.load()
    for y in range(result.height):
        for x in range(result.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha == 0:
                continue
            if is_chroma_fringe(red, green, blue):
                pixels[x, y] = (red, green, blue, 0)
    return result


def row_registration_boxes(source: Image.Image) -> list[tuple[int, int, int, int]]:
    """Find one fixed registration box per direction across all eight frames."""
    registrations: list[tuple[int, int, int, int]] = []
    for row in range(ROWS):
        union: tuple[int, int, int, int] | None = None
        for column in range(COLUMNS):
            cell = source.crop(frame_bounds(source, row, column))
            bbox = chroma_alpha(cell).getbbox()
            if bbox is None:
                raise ValueError(f"Frame {row},{column} has no foreground")
            if union is None:
                union = bbox
            else:
                union = (
                    min(union[0], bbox[0]),
                    min(union[1], bbox[1]),
                    max(union[2], bbox[2]),
                    max(union[3], bbox[3]),
                )
        if union is None:
            raise ValueError(f"Direction row {row} has no foreground")
        registrations.append(union)
    return registrations


def build_range_mask(alpha: Image.Image, start_y: int, end_y: int) -> Image.Image:
    mask = Image.new("L", alpha.size, 0)
    mask.paste(alpha.crop((0, start_y, alpha.width, end_y)), (0, start_y))
    return mask


def split_subject(
    cell: Image.Image,
    registration_box: tuple[int, int, int, int],
) -> dict[str, Image.Image]:
    alpha = chroma_alpha(cell)
    subject = cell.crop(registration_box).convert("RGBA")
    subject.putalpha(alpha.crop(registration_box))
    registration_width = registration_box[2] - registration_box[0]
    registration_height = registration_box[3] - registration_box[1]
    scaled_width = max(1, round(registration_width * TARGET_HEIGHT / registration_height))
    subject = subject.resize((scaled_width, TARGET_HEIGHT), Image.Resampling.NEAREST)
    subject = remove_chroma_fringe(subject)
    subject_alpha = subject.getchannel("A")

    split_y = round(TARGET_HEIGHT * HEAD_SPLIT_RATIO)
    lower_body_split_y = round(TARGET_HEIGHT * LOWER_BODY_SPLIT_RATIO)
    # Clothing slots use overlapping horizontal regions. They are not meant
    # to be anatomical masks; overlap prevents seams and allows future outfit
    # layers to cover upper and lower parts independently.
    masks = {
        "head": build_range_mask(subject_alpha, 0, min(TARGET_HEIGHT, split_y + SEAM_OVERLAP)),
        "torso": build_range_mask(
            subject_alpha,
            max(0, split_y - SEAM_OVERLAP),
            min(TARGET_HEIGHT, round(TARGET_HEIGHT * 0.74)),
        ),
        "arms": build_range_mask(
            subject_alpha,
            max(0, round(TARGET_HEIGHT * 0.58) - SEAM_OVERLAP),
            min(TARGET_HEIGHT, round(TARGET_HEIGHT * 0.88)),
        ),
        "lower_body": build_range_mask(
            subject_alpha,
            max(0, lower_body_split_y - SEAM_OVERLAP),
            min(TARGET_HEIGHT, round(TARGET_HEIGHT * 0.98)),
        ),
        "feet": build_range_mask(
            subject_alpha,
            max(0, round(TARGET_HEIGHT * 0.84) - SEAM_OVERLAP),
            TARGET_HEIGHT,
        ),
    }
    layers: dict[str, Image.Image] = {}
    for layer, mask in masks.items():
        image = Image.new("RGBA", subject.size, (0, 0, 0, 0))
        image.paste(subject, (0, 0), mask)
        layers[layer] = image
    return layers


def frame_bounds(source: Image.Image, row: int, column: int) -> tuple[int, int, int, int]:
    x0 = round(column * source.width / COLUMNS)
    x1 = round((column + 1) * source.width / COLUMNS)
    y0 = round(row * source.height / ROWS)
    y1 = round((row + 1) * source.height / ROWS)
    return x0, y0, x1, y1


def shift_same_size(image: Image.Image, dx: int, dy: int = 0) -> Image.Image:
    """Translate a layer inside its fixed registration canvas."""
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


def body_torso_offsets(
    source: Image.Image,
    row: int,
    registration_box: tuple[int, int, int, int],
) -> list[tuple[int, int]]:
    """Return per-frame shifts that keep the torso registration stable.

    The generated walk atlas contains an unintended whole-body slide to the
    left over the eight frames. Keep the torso's center/top fixed, while the
    arms, legs and feet retain their local pose changes.
    """
    anchors: list[tuple[float, float]] = []
    for column in range(COLUMNS):
        cell = source.crop(frame_bounds(source, row, column))
        torso = split_subject(cell, registration_box)["torso"]
        if row in {1, 3}:
            torso = torso.resize(
                (max(1, round(torso.width * SIDE_LIMB_SCALE_X)), torso.height),
                Image.Resampling.NEAREST,
            )
        bbox = torso.getchannel("A").getbbox()
        if bbox is None:
            raise ValueError(f"empty torso registration at row={row}, column={column}")
        anchors.append(((bbox[0] + bbox[2]) / 2, bbox[1]))
    target_x, target_y = anchors[0]
    return [(round(target_x - x), round(target_y - y)) for x, y in anchors]


def process_sheet(
    source: Image.Image,
    layer: str,
    registrations: list[tuple[int, int, int, int]],
) -> tuple[Image.Image, list[list[str]]]:
    atlas = Image.new("RGBA", (COLUMNS * CELL_SIZE, ROWS * CELL_SIZE), (0, 0, 0, 0))
    frame_names: list[list[str]] = []
    frame_dir = OUTPUT / f"{layer}_frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    offsets = [
        body_torso_offsets(source, row, registrations[row])
        if layer in {"torso", "arms", "lower_body", "feet"}
        else [(0, 0)] * COLUMNS
        for row in range(ROWS)
    ]

    for row in range(ROWS):
        row_names: list[str] = []
        for column in range(COLUMNS):
            cell = source.crop(frame_bounds(source, row, column))
            layers = split_subject(cell, registrations[row])
            if layer.startswith("head"):
                frame = layers["head"]
                if row in {1, 3} and HEAD_REAR_EXPAND_X > 0:
                    original_width = frame.width
                    frame = frame.resize(
                        (original_width + HEAD_REAR_EXPAND_X, frame.height),
                        Image.Resampling.NEAREST,
                    )
            else:
                frame = layers[layer]
            if layer in {"torso", "arms", "lower_body", "feet"} and row in {1, 3}:
                # The generated side poses use a wider stride than the
                # intended compact chibi silhouette. Keep the head untouched
                # and apply one uniform width reduction to both lower layers.
                scaled_layer_width = max(1, round(frame.width * SIDE_LIMB_SCALE_X))
                frame = frame.resize(
                    (scaled_layer_width, frame.height), Image.Resampling.NEAREST
                )
            if layer in {"torso", "arms", "lower_body", "feet"}:
                frame = shift_same_size(frame, *offsets[row][column])
            canvas = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
            if layer.startswith("head") and row in {1, 3}:
                original_x = CENTER_X - original_width // 2
                # Preserve the face/front edge and spend the added width on
                # the rear silhouette for each side-facing direction.
                x = original_x - HEAD_REAR_EXPAND_X if row == 1 else original_x
            else:
                x = CENTER_X - frame.width // 2
            y = BASELINE_Y - TARGET_HEIGHT
            canvas.alpha_composite(frame, (x, y))
            name = f"walk_row{row}_frame{column}.png"
            canvas.save(frame_dir / name)
            atlas.alpha_composite(canvas, (column * CELL_SIZE, row * CELL_SIZE))
            row_names.append(name)
        frame_names.append(row_names)
    return atlas, frame_names


def main() -> None:
    global SHARED_SOURCE, OUTPUT
    shared_override = os.environ.get("CHIBI_SHARED_SOURCE")
    output_override = os.environ.get("CHIBI_OUTPUT_ROOT")
    if shared_override:
        SHARED_SOURCE = Path(shared_override).resolve()
    if output_override:
        OUTPUT = Path(output_override).resolve()

    for source in (SHARED_SOURCE, MALE_HEAD_SOURCE, FEMALE_HEAD_SOURCE):
        if not source.exists():
            raise FileNotFoundError(source)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    shared = Image.open(SHARED_SOURCE).convert("RGB")
    male = Image.open(MALE_HEAD_SOURCE).convert("RGB")
    female = Image.open(FEMALE_HEAD_SOURCE).convert("RGB")

    # Register every layer against the shared full-body source. This keeps all
    # clothing slots on the same scale even when a source frame is shorter or
    # wider than its neighbors.
    registrations = row_registration_boxes(shared)

    # The neutral body always comes from the shared source. Heads vary by
    # character, while the remaining slots are intentionally outfit-ready.
    layer_atlases: dict[str, Image.Image] = {}
    layer_frames: dict[str, list[list[str]]] = {}
    for layer in ("torso", "arms", "lower_body", "feet"):
        layer_atlases[layer], layer_frames[layer] = process_sheet(
            shared, layer, registrations
        )
    male_atlas, male_frames = process_sheet(male, "head_male", registrations)
    female_atlas, female_frames = process_sheet(female, "head_female", registrations)
    for layer, atlas in layer_atlases.items():
        atlas.save(OUTPUT / f"{layer}_walk_4way.png")
    male_atlas.save(OUTPUT / "head_male_walk_4way.png")
    female_atlas.save(OUTPUT / "head_female_walk_4way.png")

    manifest = {
        "variant": "chibi_qqtang_bighead",
        "sources": {
            "shared_body": SHARED_SOURCE.relative_to(ROOT).as_posix(),
            "male_head": MALE_HEAD_SOURCE.relative_to(ROOT).as_posix(),
            "female_head": FEMALE_HEAD_SOURCE.relative_to(ROOT).as_posix(),
        },
        "cell_size": [CELL_SIZE, CELL_SIZE],
        "columns": COLUMNS,
        "rows": ROWS,
        "frame_count_per_direction": COLUMNS,
        "row_directions": ["front", "right", "back", "left"],
        "layer_atlases": {
            layer: (OUTPUT / f"{layer}_walk_4way.png").relative_to(ROOT).as_posix()
            for layer in layer_atlases
        },
        "head_atlases": {
            "male": (OUTPUT / "head_male_walk_4way.png").relative_to(ROOT).as_posix(),
            "female": (OUTPUT / "head_female_walk_4way.png").relative_to(ROOT).as_posix(),
        },
        "layer_frame_directories": {
            layer: (OUTPUT / f"{layer}_frames").relative_to(ROOT).as_posix()
            for layer in layer_atlases
        },
        "head_frame_directories": {
            "male": (OUTPUT / "head_male_frames").relative_to(ROOT).as_posix(),
            "female": (OUTPUT / "head_female_frames").relative_to(ROOT).as_posix(),
        },
        "target_subject_height": TARGET_HEIGHT,
        "baseline_y": BASELINE_Y,
        "registration_mode": "fixed_union_box_plus_torso_anchor_per_direction",
        "torso_anchor_offsets": {
            "description": "per-frame shifts applied consistently to all body layers",
            "reference_frame": 0,
        },
        "registration_boxes": registrations,
        "side_limb_scale_x": SIDE_LIMB_SCALE_X,
        "head_rear_expand_x": HEAD_REAR_EXPAND_X,
        "head_split_ratio": HEAD_SPLIT_RATIO,
        "lower_body_split_ratio": LOWER_BODY_SPLIT_RATIO,
        "frames": {
            **layer_frames,
            "head_male": male_frames,
            "head_female": female_frames,
        },
        "neutral_base": True,
        "no_ears": True,
        "separate_head_body": True,
        "female_blush_layer": "optional independent overlay; not baked into the base head",
    }
    (OUTPUT / "animation_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
