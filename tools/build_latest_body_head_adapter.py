from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BODY_SOURCE = ROOT / "prototype/assets/characters/generated/female_adventurer_reference_mannequin_v1"
HEAD_SOURCE = ROOT / "prototype/assets/characters/rebuild_atlas_v1_runtime/male"
OUTPUT = ROOT / "prototype/assets/characters/generated/female_adventurer_reference_mannequin_v1_adapted"
DIRECTIONS = ("front", "right", "back", "left")
FRAME_COUNT = 8
CELL_SIZE = 64
BODY_CUT_Y = 30


def load_rgba(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    if image.size != (CELL_SIZE, CELL_SIZE):
        raise ValueError(f"expected 64x64 frame, got {image.size}: {path}")
    return image


def body_only(source: Image.Image) -> Image.Image:
    result = source.copy()
    alpha = result.getchannel("A")
    mask = Image.new("L", result.size, 0)
    mask.paste(alpha.crop((0, BODY_CUT_Y, CELL_SIZE, CELL_SIZE)), (0, BODY_CUT_Y))
    result.putalpha(mask)
    return result


def head_layer(layer: str, row: int, frame: int) -> Image.Image:
    return load_rgba(HEAD_SOURCE / f"{layer}_frames/walk_row{row}_frame{frame}.png")


def flatten(body: Image.Image, row: int, frame: int) -> Image.Image:
    result = body.copy()
    result.alpha_composite(head_layer("face_base", row, frame))
    result.alpha_composite(head_layer("ears", row, frame))
    result.alpha_composite(head_layer("face", row, frame))
    return result


def save_sheet(frames: list[Image.Image], path: Path) -> None:
    sheet = Image.new("RGBA", (CELL_SIZE * FRAME_COUNT, CELL_SIZE))
    for frame, image in enumerate(frames):
        sheet.alpha_composite(image, (frame * CELL_SIZE, 0))
    sheet.save(path)


def main() -> int:
    if not BODY_SOURCE.exists():
        raise FileNotFoundError(BODY_SOURCE)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    body_sheets: dict[str, str] = {}
    composite_sheets: dict[str, str] = {}

    for row, direction in enumerate(DIRECTIONS):
        body_dir = OUTPUT / "body_frames"
        body_dir.mkdir(parents=True, exist_ok=True)
        body_frames: list[Image.Image] = []
        composite_frames: list[Image.Image] = []
        for frame in range(FRAME_COUNT):
            source = load_rgba(BODY_SOURCE / direction / f"frame{frame}.png")
            body = body_only(source)
            body_frames.append(body)
            composite_frames.append(flatten(body, row, frame))
            body.save(body_dir / f"walk_row{row}_frame{frame}.png")
        body_sheet = OUTPUT / f"body_walk_{direction}.png"
        composite_sheet = OUTPUT / f"calibrated_head_body_{direction}.png"
        save_sheet(body_frames, body_sheet)
        save_sheet(composite_frames, composite_sheet)
        body_sheets[direction] = body_sheet.relative_to(ROOT).as_posix()
        composite_sheets[direction] = composite_sheet.relative_to(ROOT).as_posix()

    manifest = {
        "schema": "latest_generated_body_head_adapter_v1",
        "status": "adapter_candidate_for_head_review",
        "cell_size": [CELL_SIZE, CELL_SIZE],
        "frame_count": FRAME_COUNT,
        "directions": list(DIRECTIONS),
        "body_source": BODY_SOURCE.relative_to(ROOT).as_posix(),
        "head_source": HEAD_SOURCE.relative_to(ROOT).as_posix(),
        "body_cut_y": BODY_CUT_Y,
        "body_baseline_y": 59,
        "body_sheets": body_sheets,
        "calibrated_head_body_sheets": composite_sheets,
        "notes": "The latest generated body is cut below its provisional head and composed with the calibrated runtime head. This output is for interface validation; it does not replace the calibrated head assets.",
    }
    (OUTPUT / "adapter_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"LATEST_BODY_HEAD_ADAPTER_PASS directions={len(DIRECTIONS)} frames={len(DIRECTIONS) * FRAME_COUNT} cut_y={BODY_CUT_Y}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
