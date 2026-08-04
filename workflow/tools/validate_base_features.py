from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
FEATURE_ROOT = ROOT / "prototype" / "assets" / "characters" / "base_features_v1"
EXPECTED_SIZE = (64, 64)
GENDERS = ("male", "female")
ROWS = 4
COLUMNS = 8


def bbox_or_none(path: Path):
    with Image.open(path) as image:
        if image.size != EXPECTED_SIZE or image.mode != "RGBA":
            raise ValueError(f"unexpected base feature format: {path}")
        return image.getchannel("A").getbbox()


def validate_layer(gender: str, layer: str) -> int:
    directory = FEATURE_ROOT / gender / f"{layer}_frames"
    total = 0
    for row in range(ROWS):
        for frame in range(COLUMNS):
            path = directory / f"walk_row{row}_frame{frame}.png"
            if not path.exists():
                raise ValueError(f"missing base feature frame: {path}")
            bbox = bbox_or_none(path)
            if layer == "face" and row == 2:
                if bbox is not None:
                    raise ValueError(f"back face must be empty: {path}")
            else:
                if bbox is None:
                    raise ValueError(f"base feature frame is empty: {path}")
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
                if layer == "face":
                    max_width, max_height = ((20, 8) if row == 0 else (7, 9))
                else:
                    if row == 0:
                        max_width, max_height = (32, 12)
                    elif row == 2:
                        max_width, max_height = (34, 12)
                    else:
                        max_width, max_height = (8, 12)
                if width > max_width or height > max_height:
                    raise ValueError(f"base feature exceeds anchor limit: {path} bbox={bbox}")
            total += 1
    return total


def main() -> int:
    manifest_path = FEATURE_ROOT / "base_features_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("randomization_ready") is not False:
        raise ValueError("base feature manifest must remain a pre-randomization candidate")
    if manifest.get("no_nose") is not True or manifest.get("no_mouth") is not True:
        raise ValueError("base feature manifest does not enforce no nose/no mouth")
    total = 0
    for gender in GENDERS:
        total += validate_layer(gender, "face")
        total += validate_layer(gender, "ear")
    print(f"BASE_FEATURE_VALIDATION_PASS genders=2 component_frames={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
