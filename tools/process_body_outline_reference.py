from __future__ import annotations

import json
import argparse
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
FRAME_COUNT = 8
CELL_SIZE = 64
TARGET_HEIGHT = 30
BASELINE_Y = 58


def fit_frame(source: Image.Image, frame_index: int) -> Image.Image:
    left = round(frame_index * source.width / FRAME_COUNT)
    right = round((frame_index + 1) * source.width / FRAME_COUNT)
    frame = source.crop((left, 0, right, source.height)).convert("RGBA")
    alpha = frame.getchannel("A").point(lambda value: 255 if value >= 32 else 0)
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError(f"empty outline frame {frame_index}")
    frame = frame.crop(bbox)
    alpha = alpha.crop(bbox)
    scale = TARGET_HEIGHT / frame.height
    width = max(1, round(frame.width * scale))
    frame = frame.resize((width, TARGET_HEIGHT), Image.Resampling.LANCZOS)
    alpha = alpha.resize((width, TARGET_HEIGHT), Image.Resampling.LANCZOS)
    frame.putalpha(alpha)
    result = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    result.alpha_composite(frame, ((CELL_SIZE - width) // 2, BASELINE_Y - TARGET_HEIGHT))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v1", choices=["v1", "v2"])
    args = parser.parse_args()
    source_path = ROOT / f"prototype/assets/characters/generated/walk_body_outline_split_{args.version}.png"
    output = ROOT / f"prototype/assets/characters/generated/body_outline_split_{args.version}_right_walk_8.png"
    contact = ROOT / f"prototype/preview/assets/body_outline_split_{args.version}_right_contact.png"
    manifest = ROOT / f"prototype/assets/characters/generated/body_outline_split_{args.version}_manifest.json"
    source_image = Image.open(source_path).convert("RGBA")
    frames = [fit_frame(source_image, index) for index in range(FRAME_COUNT)]
    sheet = Image.new("RGBA", (CELL_SIZE * FRAME_COUNT, CELL_SIZE), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        sheet.alpha_composite(frame, (index * CELL_SIZE, 0))
    output.parent.mkdir(parents=True, exist_ok=True)
    contact.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    sheet.resize((CELL_SIZE * FRAME_COUNT * 4, CELL_SIZE * 4), Image.Resampling.NEAREST).save(contact)
    manifest.write_text(
        json.dumps(
            {
                "schema": "body_outline_split_v1",
                "source": source_path.relative_to(ROOT).as_posix(),
                "direction": "right",
                "frames": FRAME_COUNT,
                "cell_size": [CELL_SIZE, CELL_SIZE],
                "baseline_y": BASELINE_Y,
                "marker_parts": ["front_arm", "rear_arm", "front_leg", "rear_leg"],
                "status": "awaiting_manual_split_lines",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"BODY_OUTLINE_REFERENCE_PASS version={args.version} frames=8 status=awaiting_manual_split_lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
