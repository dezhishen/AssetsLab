"""Build the small, current-only AssetsLab preview asset set."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "prototype/preview/assets"
BODY_ROOT = ROOT / "prototype/assets/characters/generated/female_adventurer_reference_mannequin_v1_adapted/body_frames"
HEAD_ROOT = ROOT / "prototype/assets/characters/rebuild_atlas_v1_runtime/male"
VERTICAL_ROOT = ROOT / "prototype/assets/characters/generated/body_vertical_update_v1/runtime"
STYLE_ROOT = ROOT / "prototype/assets/characters/generated/skill_pixel_art_experiment_v1"
CAPTURE_GIF = ROOT / "prototype/test_output/movement_vertical_body_candidate.gif"
STAGED_CAPTURE_GIF = OUTPUT / "movement_vertical_body_candidate.gif"
DIRECTIONS = ("front", "right", "back", "left")


def rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def clear_output() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for child in OUTPUT.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def load_frames(root: Path, pattern: str) -> list[list[Image.Image]]:
    return [
        [rgba(root / pattern.format(row=row, frame=frame)) for frame in range(8)]
        for row in range(4)
    ]


def load_head_frames() -> dict[str, list[list[Image.Image]]]:
    return {
        layer: load_frames(HEAD_ROOT / f"{layer}_frames", "walk_row{row}_frame{frame}.png")
        for layer in ("face_base", "ears", "face")
    }


def compose(
    body: Image.Image,
    head_frames: dict[str, list[list[Image.Image]]],
    row: int,
    frame: int,
    offset: tuple[int, int],
) -> Image.Image:
    result = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    result.alpha_composite(body)
    for layer in ("face_base", "ears", "face"):
        result.alpha_composite(head_frames[layer][row][frame], dest=offset)
    return result


def sheet(frames: list[list[Image.Image]]) -> Image.Image:
    output = Image.new("RGBA", (512, 256), (0, 0, 0, 0))
    for row in range(4):
        for frame in range(8):
            output.alpha_composite(frames[row][frame], dest=(frame * 64, row * 64))
    return output


def strip(frames: list[Image.Image]) -> Image.Image:
    output = Image.new("RGBA", (len(frames) * 64, 64), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        output.alpha_composite(frame, dest=(index * 64, 0))
    return output


def gif(frames: list[Image.Image], path: Path) -> None:
    enlarged = [frame.resize((256, 256), Image.Resampling.NEAREST) for frame in frames]
    enlarged[0].save(path, save_all=True, append_images=enlarged[1:], duration=100, loop=0, disposal=2)


def load_offsets() -> dict[str, tuple[int, int]]:
    payload = json.loads((HEAD_ROOT / "runtime_manifest.json").read_text(encoding="utf-8"))
    return {
        direction: tuple(payload.get("body_anchor_offsets", {}).get(direction, [0, 0]))
        for direction in DIRECTIONS
    }


def main() -> int:
    clear_output()
    body_frames = load_frames(BODY_ROOT, "walk_row{row}_frame{frame}.png")
    head_frames = load_head_frames()
    offsets = load_offsets()

    body_sheet = sheet(body_frames)
    character_frames = [
        [compose(body_frames[row][frame], head_frames, row, frame, offsets[DIRECTIONS[row]]) for frame in range(8)]
        for row in range(4)
    ]
    head_only_frames = [
        [compose(Image.new("RGBA", (64, 64), (0, 0, 0, 0)), head_frames, row, frame, (0, 0)) for frame in range(8)]
        for row in range(4)
    ]
    character_sheet = sheet(character_frames)
    head_sheet = sheet(head_only_frames)
    body_sheet.save(OUTPUT / "current_body_4way_8frames.png")
    character_sheet.save(OUTPUT / "current_character_4way_8frames.png")
    head_sheet.save(OUTPUT / "current_head_4way_8frames.png")
    gif([character_frames[row][frame] for row in range(4) for frame in range(8)], OUTPUT / "current_character_walk_4way.gif")

    for row, direction in enumerate(DIRECTIONS):
        character_frames[row][0].resize((512, 512), Image.Resampling.NEAREST).save(OUTPUT / f"current_{direction}.png")
        body_frames[row][0].resize((512, 512), Image.Resampling.NEAREST).save(OUTPUT / f"current_{direction}_body.png")

    vertical_front = [rgba(VERTICAL_ROOT / "front_frames" / f"frame{frame}.png") for frame in range(8)]
    vertical_back = [rgba(VERTICAL_ROOT / "back_frames" / f"frame{frame}.png") for frame in range(8)]
    vertical_front_character = [compose(frame, head_frames, 0, index, (0, 0)) for index, frame in enumerate(vertical_front)]
    vertical_back_character = [compose(frame, head_frames, 2, index, (0, 0)) for index, frame in enumerate(vertical_back)]
    strip(vertical_front_character).save(OUTPUT / "vertical_front_8frames.png")
    strip(vertical_back_character).save(OUTPUT / "vertical_back_8frames.png")
    gif(vertical_front_character + vertical_back_character, OUTPUT / "vertical_candidate_rebuilt.gif")
    if CAPTURE_GIF.exists():
        shutil.copy2(CAPTURE_GIF, OUTPUT / "movement_vertical_body_candidate.gif")
    elif STAGED_CAPTURE_GIF.exists():
        shutil.copy2(STAGED_CAPTURE_GIF, OUTPUT / "movement_vertical_body_candidate.gif")

    style_image = STYLE_ROOT / "turnaround_db16_transparent.png"
    if style_image.exists():
        shutil.copy2(style_image, OUTPUT / "style_experiment_db16.png")

    manifest = {
        "schema": "assetslab_current_preview_v2",
        "status": "current_test_base_only",
        "test_base": {
            "body": "prototype/assets/characters/generated/female_adventurer_reference_mannequin_v1_adapted/body_frames",
            "head": "prototype/assets/characters/rebuild_atlas_v1_runtime/male",
            "body_registration": "runtime_manifest.json body_anchor_offsets",
            "directions": list(DIRECTIONS),
            "frames_per_direction": 8,
        },
        "vertical_candidate": {
            "source": "prototype/assets/characters/generated/body_vertical_update_v1/runtime",
            "head_anchor_offsets": {"front": [0, 0], "back": [0, 0]},
            "status": "candidate_for_visual_review",
        },
        "excluded": "legacy bodies, RGS proxies, skeleton tests, old generated walk GIFs, and retired preview pages",
        "files": sorted(path.name for path in OUTPUT.iterdir() if path.is_file()),
    }
    (OUTPUT / "current_preview_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("CURRENT_PREVIEW_ASSETS_PASS base=4x8 vertical=2x8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
