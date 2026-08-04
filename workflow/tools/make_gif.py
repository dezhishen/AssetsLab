from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a GIF from numbered PNG frames.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fps", required=True, type=int)
    args = parser.parse_args()

    frames = sorted(args.input.glob("frame_*.png"))
    if not frames:
        raise SystemExit(f"No PNG frames found in {args.input}")
    if args.fps <= 0:
        raise SystemExit("FPS must be positive")

    images = [Image.open(path).convert("RGB") for path in frames]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        args.output,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        duration=round(1000 / args.fps),
        loop=0,
        optimize=False,
        disposal=2,
    )
    for image in images:
        image.close()
    print(f"GIF_PASS frames={len(frames)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
