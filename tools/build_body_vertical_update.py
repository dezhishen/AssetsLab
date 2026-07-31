"""Normalize imagegen front/back walk strips into 64x64 candidate body frames.

The generated strips stay as source evidence. Runtime-sized frames are written
under the candidate directory and are never installed over the authoritative
body adapter automatically.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "prototype/assets/characters/generated/body_vertical_update_v1"


def alpha_groups(image: Image.Image, threshold: int = 20) -> list[tuple[int, int]]:
    alpha = image.getchannel("A")
    width, height = image.size
    columns = [
        any(alpha.getpixel((x, y)) > threshold for y in range(height))
        for x in range(width)
    ]
    groups: list[tuple[int, int]] = []
    start: int | None = None
    for x, active in enumerate(columns + [False]):
        if active and start is None:
            start = x
        elif not active and start is not None:
            groups.append((start, x))
            start = None
    return groups


def normalize_strip(source: Path, output_dir: Path, direction: str) -> list[str]:
    strip = Image.open(source).convert("RGBA")
    groups = alpha_groups(strip)
    if len(groups) != 8:
        raise ValueError(f"{source.name}: expected 8 alpha groups, found {len(groups)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for frame, (left, right) in enumerate(groups):
        crop = strip.crop((left, 0, right, strip.height))
        bbox = crop.getchannel("A").getbbox()
        if bbox is None:
            raise ValueError(f"{source.name}: frame {frame} has no visible pixels")
        crop = crop.crop(bbox)
        target_height = 30
        scale = target_height / crop.height
        target_width = max(1, round(crop.width * scale))
        resized = crop.resize((target_width, target_height), Image.Resampling.NEAREST)

        canvas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        x = (64 - target_width) // 2
        y = 60 - target_height
        canvas.alpha_composite(resized, (x, y))
        name = f"frame{frame}.png"
        canvas.save(output_dir / name)
        written.append(name)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    input_dir = args.input_dir if args.input_dir.is_absolute() else ROOT / args.input_dir
    output_dir = args.output_dir or input_dir / "runtime"
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir

    front = input_dir / "front_transparent.png"
    back = input_dir / "back_transparent.png"
    if not front.exists() or not back.exists():
        raise FileNotFoundError("front_transparent.png and back_transparent.png are required")

    front_files = normalize_strip(front, output_dir / "front_frames", "front")
    back_files = normalize_strip(back, output_dir / "back_frames", "back")
    manifest = {
        "schema": "body_vertical_update_candidate_v1",
        "status": "candidate_for_visual_review",
        "source": {
            "front": str(front.relative_to(ROOT)).replace("\\", "/"),
            "back": str(back.relative_to(ROOT)).replace("\\", "/"),
        },
        "directions": {"front": front_files, "back": back_files},
        "frame_count": 8,
        "canvas": [64, 64],
        "body_bbox_target": [None, 30, None, 60],
        "normalization": "alpha-group crop, nearest-neighbor scale to 30px height, baseline y=60",
        "runtime_policy": "candidate only; do not replace the latest generated body adapter until review",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"BODY_VERTICAL_UPDATE_PASS front=8 back=8 output={output_dir}")


if __name__ == "__main__":
    main()
