from __future__ import annotations

import argparse
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "prototype" / "test_output" / "random_appearance"
ROWS = 4
COLUMNS = 8
CELL_SIZE = 64
MODULUS = 2_147_483_647
MULTIPLIER = 1_103_515_245
INCREMENT = 12_345
ALL_VARIANTS = [0, 1, 2, 3, 4, 5, 6, 7]
MALE_VARIANTS = [0, 2, 4, 6]
LAYERS = ("feet", "lower_body", "arms", "torso", "ear", "head", "face")


def variant_for_seed(seed: int, female: bool) -> int:
    state = (seed * MULTIPLIER + INCREMENT) % MODULUS
    candidates = ALL_VARIANTS if female else MALE_VARIANTS
    return candidates[state % len(candidates)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate random appearance test package(s).")
    parser.add_argument("--seed", type=int, help="Optional seed for a reproducible package.")
    parser.add_argument("--female", action="store_true")
    parser.add_argument("--both", action="store_true", help="Generate matching male and female packages.")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def frame_path(asset_root: Path, layer: str, variant: int, female: bool, row: int, column: int) -> Path:
    filename = f"walk_row{row}_frame{column}.png"
    if layer == "head":
        return asset_root / f"head_{'female' if female else 'male'}_frames" / filename
    if layer in {"ear", "face"}:
        return ROOT / "prototype" / "assets" / "characters" / "faces" / f"{layer}_{variant:02d}" / "frames" / filename
    return asset_root / f"{layer}_frames" / filename


def compose_frame(asset_root: Path, variant: int, female: bool, row: int, column: int) -> Image.Image:
    composite = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    for layer in LAYERS:
        path = frame_path(asset_root, layer, variant, female, row, column)
        with Image.open(path) as layer_image:
            composite.alpha_composite(layer_image.convert("RGBA"))
    return composite


def generate_package(
    *, seed: int, female: bool, compact: bool, output: Path
) -> int:
    variant = variant_for_seed(seed, female)
    asset_name = "chibi_compact" if compact else "chibi"
    asset_root = ROOT / "prototype" / "assets" / "characters" / asset_name
    output = output.resolve()
    frames_root = output / "frames"
    frames_root.mkdir(parents=True, exist_ok=True)

    atlas = Image.new("RGBA", (COLUMNS * CELL_SIZE, ROWS * CELL_SIZE), (0, 0, 0, 0))
    for row in range(ROWS):
        for column in range(COLUMNS):
            composite = compose_frame(asset_root, variant, female, row, column)
            composite.save(frames_root / f"walk_row{row}_frame{column}.png")
            atlas.alpha_composite(composite, (column * CELL_SIZE, row * CELL_SIZE))
    atlas.save(output / "character_walk_4way.png")

    preview = Image.new("RGBA", (4 * 128, 2 * 128), (38, 42, 55, 255))
    for direction_row in range(ROWS):
        composite = compose_frame(asset_root, variant, female, direction_row, 0)
        preview.alpha_composite(
            composite.resize((128, 128), Image.Resampling.NEAREST),
            ((direction_row % 4) * 128, (direction_row // 4) * 128),
        )
    preview.save(output / "preview.png")

    manifest = {
        "generator": "generate_random_appearance.py",
        "generator_version": 1,
        "seed": seed,
        "gender": "female" if female else "male",
        "asset_variant": asset_name,
        "appearance_variant": variant,
        "layer_order": list(LAYERS),
        "cell_size": [CELL_SIZE, CELL_SIZE],
        "directions": ["front", "right", "back", "left"],
        "frame_count_per_direction": COLUMNS,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_files": {
            "atlas": "character_walk_4way.png",
            "preview": "preview.png",
            "frames": "frames",
        },
    }
    (output / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(f"RANDOM_APPEARANCE_PACKAGE={output}")
    print(f"RANDOM_APPEARANCE_VARIANT_{'FEMALE' if female else 'MALE'}={variant}")
    return 0


def main() -> int:
    args = parse_args()
    seed = args.seed if args.seed is not None else secrets.randbits(31)
    seed = seed % MODULUS
    if args.both:
        generate_package(seed=seed, female=False, compact=args.compact, output=args.output / "male")
        generate_package(seed=seed, female=True, compact=args.compact, output=args.output / "female")
    else:
        generate_package(seed=seed, female=args.female, compact=args.compact, output=args.output)
    print(f"RANDOM_APPEARANCE_SEED={seed}")
    print(f"RANDOM_APPEARANCE_OUTPUT={args.output.resolve()}")
    print("RANDOM_APPEARANCE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
