from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SIZE = (64, 64)
ROWS = 4
COLUMNS = 8
MODULUS = 2_147_483_647
MULTIPLIER = 1_103_515_245
INCREMENT = 12_345
MALE_VARIANTS = [0, 2, 4, 6]


def expected_variant(seed: int, gender: str) -> int:
    state = (seed * MULTIPLIER + INCREMENT) % MODULUS
    variants = list(range(8)) if gender == "female" else MALE_VARIANTS
    return variants[state % len(variants)]


def validate_package(package_root: Path) -> int:
    manifest_path = package_root / "run_manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"missing random package manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    gender = manifest.get("gender")
    seed = manifest.get("seed")
    variant = manifest.get("appearance_variant")
    if gender not in {"male", "female"} or not isinstance(seed, int) or not isinstance(variant, int):
        raise ValueError(f"invalid random package metadata: {manifest_path}")
    if variant != expected_variant(seed, gender):
        raise ValueError(f"seed/variant mismatch in {manifest_path}")

    frames_root = package_root / "frames"
    total = 0
    non_empty = 0
    for row in range(ROWS):
        for column in range(COLUMNS):
            path = frames_root / f"walk_row{row}_frame{column}.png"
            if not path.exists():
                raise ValueError(f"missing random composite frame: {path}")
            with Image.open(path) as image:
                if image.size != EXPECTED_SIZE or image.mode != "RGBA":
                    raise ValueError(f"unexpected random composite format: {path}")
                if image.getchannel("A").getbbox() is not None:
                    non_empty += 1
            total += 1
    if non_empty != total:
        raise ValueError(f"random composite contains empty frames: {package_root}")
    for name in ("character_walk_4way.png", "preview.png"):
        if not (package_root / name).exists():
            raise ValueError(f"missing random composite output: {package_root / name}")
    return total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate generated random appearance package(s).")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--both", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    packages = [root / "male", root / "female"] if args.both else [root]
    total = sum(validate_package(package) for package in packages)
    print(f"RANDOM_APPEARANCE_VALIDATION_PASS packages={len(packages)} frames={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
