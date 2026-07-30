from __future__ import annotations

import os
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ASSET_VARIANT = os.environ.get("CHIBI_ASSET_ROOT", "chibi")
CHARACTER_ROOT = ROOT / "prototype" / "assets" / "characters" / ASSET_VARIANT
ROWS = 4
COLUMNS = 8
EXPECTED_SIZE = (64, 64)
LAYER_RULES = {
    "torso": (28, 38, 34, 48),
    "arms": (32, 44, 42, 56),
    "lower_body": (36, 48, 46, 60),
    "feet": (44, 56, 50, 62),
    "head_male": (0, 14, 20, 42),
    "head_female": (0, 14, 20, 42),
}


def validate_layer(layer: str, y_range: tuple[int, int], baseline_range: tuple[int, int]) -> int:
    directory = CHARACTER_ROOT / f"{layer}_frames"
    frame_count = 0
    for row in range(ROWS):
        for column in range(COLUMNS):
            path = directory / f"walk_row{row}_frame{column}.png"
            if not path.exists():
                raise ValueError(f"missing frame: {path}")
            with Image.open(path) as image:
                if image.size != EXPECTED_SIZE:
                    raise ValueError(f"unexpected size for {path}: {image.size}")
                bbox = image.getchannel("A").getbbox()
                if bbox is None:
                    raise ValueError(f"empty frame: {path}")
                if not y_range[0] <= bbox[1] <= y_range[1]:
                    raise ValueError(f"unstable top seam for {path}: {bbox}")
                if not baseline_range[0] <= bbox[3] <= baseline_range[1]:
                    raise ValueError(f"unstable baseline for {path}: {bbox}")
            frame_count += 1
    return frame_count


def main() -> int:
    total = 0
    for layer, (top_min, top_max, bottom_min, bottom_max) in LAYER_RULES.items():
        total += validate_layer(layer, (top_min, top_max), (bottom_min, bottom_max))
    print(f"CHIBI_FRAME_VALIDATION_PASS variant={ASSET_VARIANT} frames={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
