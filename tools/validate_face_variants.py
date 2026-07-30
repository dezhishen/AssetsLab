from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CHARACTER_ROOT = ROOT / "prototype" / "assets" / "characters" / "faces"
EXPECTED_SIZE = (64, 64)
VARIANTS = 8
ROWS = 4
COLUMNS = 8


def main() -> int:
    manifest_path = CHARACTER_ROOT / "face_manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"missing manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("variant_count") != VARIANTS:
        raise ValueError("manifest variant count is not 8")
    if "nose" not in manifest.get("forbidden_components", []) or "mouth" not in manifest.get("forbidden_components", []):
        raise ValueError("face manifest does not enforce no nose/no mouth")

    total = 0
    for variant_id in range(VARIANTS):
        roots = {
            "face": CHARACTER_ROOT / f"face_{variant_id:02d}" / "frames",
            "ear": CHARACTER_ROOT / f"ear_{variant_id:02d}" / "frames",
        }
        for component, frame_root in roots.items():
            front_pixels = 0
            rear_pixels = 0
            for row in range(ROWS):
                for column in range(COLUMNS):
                    path = frame_root / f"walk_row{row}_frame{column}.png"
                    if not path.exists():
                        raise ValueError(f"missing {component} frame: {path}")
                    with Image.open(path) as image:
                        if image.size != EXPECTED_SIZE or image.mode != "RGBA":
                            raise ValueError(f"unexpected {component} frame format: {path}: {image.size} {image.mode}")
                        rgba_pixels = [
                            image.getpixel((x, y))
                            for y in range(image.height)
                            for x in range(image.width)
                        ]
                        pixels = sum(1 for _red, _green, _blue, alpha in rgba_pixels if alpha > 0)
                        if row == 0:
                            front_pixels += pixels
                        else:
                            rear_pixels += pixels
                        if any(
                            red > 170 and blue > 95 and green < 95
                            for red, green, blue, _alpha in rgba_pixels
                            if _alpha > 32
                        ):
                            raise ValueError(f"magenta fringe remains in {path}")
                    total += 1
            if front_pixels == 0:
                raise ValueError(f"front {component} variant is empty: {variant_id}")
            if rear_pixels != 0:
                raise ValueError(f"non-front {component} pixels found in variant: {variant_id}")
    print(f"FACE_EAR_VARIANT_VALIDATION_PASS variants={VARIANTS} component_frames={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
