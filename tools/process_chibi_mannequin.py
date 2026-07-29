from __future__ import annotations

import json
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
LEG_SPLIT_RATIO = 0.66
SEAM_OVERLAP = 2


def chroma_alpha(cell: Image.Image) -> Image.Image:
    """Remove generated magenta while preserving the neutral ivory mannequin."""
    rgb = cell.convert("RGB")
    alpha = Image.new("L", rgb.size, 0)
    source = rgb.load()
    target = alpha.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            red, green, blue = source[x, y]
            is_magenta = red > 170 and blue > 130 and green < 100 and blue > green * 1.5
            if not is_magenta:
                target[x, y] = 255
    return alpha


def split_subject(cell: Image.Image) -> tuple[Image.Image, Image.Image, Image.Image]:
    alpha = chroma_alpha(cell)
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError("Generated frame has no foreground")

    subject = cell.crop(bbox).convert("RGBA")
    subject.putalpha(alpha.crop(bbox))
    scaled_width = max(1, round(subject.width * TARGET_HEIGHT / subject.height))
    subject = subject.resize((scaled_width, TARGET_HEIGHT), Image.Resampling.NEAREST)
    subject_alpha = subject.getchannel("A")

    split_y = round(TARGET_HEIGHT * HEAD_SPLIT_RATIO)
    leg_split_y = round(TARGET_HEIGHT * LEG_SPLIT_RATIO)
    head_end = min(TARGET_HEIGHT, split_y + SEAM_OVERLAP)
    body_start = max(0, split_y - SEAM_OVERLAP)
    body_end = min(TARGET_HEIGHT, leg_split_y + SEAM_OVERLAP)
    leg_start = max(0, leg_split_y - SEAM_OVERLAP)
    head_alpha = Image.new("L", subject.size, 0)
    body_alpha = Image.new("L", subject.size, 0)
    leg_alpha = Image.new("L", subject.size, 0)
    head_alpha.paste(subject_alpha.crop((0, 0, scaled_width, head_end)), (0, 0))
    body_alpha.paste(
        subject_alpha.crop((0, body_start, scaled_width, body_end)),
        (0, body_start),
    )
    leg_alpha.paste(
        subject_alpha.crop((0, leg_start, scaled_width, TARGET_HEIGHT)),
        (0, leg_start),
    )

    head = Image.new("RGBA", subject.size, (0, 0, 0, 0))
    body = Image.new("RGBA", subject.size, (0, 0, 0, 0))
    leg = Image.new("RGBA", subject.size, (0, 0, 0, 0))
    head.paste(subject, (0, 0), head_alpha)
    body.paste(subject, (0, 0), body_alpha)
    leg.paste(subject, (0, 0), leg_alpha)
    return head, body, leg


def frame_bounds(source: Image.Image, row: int, column: int) -> tuple[int, int, int, int]:
    x0 = round(column * source.width / COLUMNS)
    x1 = round((column + 1) * source.width / COLUMNS)
    y0 = round(row * source.height / ROWS)
    y1 = round((row + 1) * source.height / ROWS)
    return x0, y0, x1, y1


def process_sheet(source: Image.Image, layer: str) -> tuple[Image.Image, list[list[str]]]:
    atlas = Image.new("RGBA", (COLUMNS * CELL_SIZE, ROWS * CELL_SIZE), (0, 0, 0, 0))
    frame_names: list[list[str]] = []
    frame_dir = OUTPUT / f"{layer}_frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    for row in range(ROWS):
        row_names: list[str] = []
        for column in range(COLUMNS):
            cell = source.crop(frame_bounds(source, row, column))
            head, body, leg = split_subject(cell)
            if layer.startswith("head"):
                frame = head
            elif layer == "leg":
                frame = leg
            else:
                frame = body
            canvas = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
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
    for source in (SHARED_SOURCE, MALE_HEAD_SOURCE, FEMALE_HEAD_SOURCE):
        if not source.exists():
            raise FileNotFoundError(source)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    shared = Image.open(SHARED_SOURCE).convert("RGB")
    male = Image.open(MALE_HEAD_SOURCE).convert("RGB")
    female = Image.open(FEMALE_HEAD_SOURCE).convert("RGB")

    # The body always comes from the shared neutral source. Only the head varies.
    body_atlas, body_frames = process_sheet(shared, "body")
    leg_atlas, leg_frames = process_sheet(shared, "leg")
    male_atlas, male_frames = process_sheet(male, "head_male")
    female_atlas, female_frames = process_sheet(female, "head_female")
    body_atlas.save(OUTPUT / "body_walk_4way.png")
    leg_atlas.save(OUTPUT / "leg_walk_4way.png")
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
        "body_atlas": (OUTPUT / "body_walk_4way.png").relative_to(ROOT).as_posix(),
        "leg_atlas": (OUTPUT / "leg_walk_4way.png").relative_to(ROOT).as_posix(),
        "head_atlases": {
            "male": (OUTPUT / "head_male_walk_4way.png").relative_to(ROOT).as_posix(),
            "female": (OUTPUT / "head_female_walk_4way.png").relative_to(ROOT).as_posix(),
        },
        "body_frame_directory": (OUTPUT / "body_frames").relative_to(ROOT).as_posix(),
        "leg_frame_directory": (OUTPUT / "leg_frames").relative_to(ROOT).as_posix(),
        "head_frame_directories": {
            "male": (OUTPUT / "head_male_frames").relative_to(ROOT).as_posix(),
            "female": (OUTPUT / "head_female_frames").relative_to(ROOT).as_posix(),
        },
        "target_subject_height": TARGET_HEIGHT,
        "baseline_y": BASELINE_Y,
        "head_split_ratio": HEAD_SPLIT_RATIO,
        "leg_split_ratio": LEG_SPLIT_RATIO,
        "frames": {
            "body": body_frames,
            "leg": leg_frames,
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
