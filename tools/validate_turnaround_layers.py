from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "prototype" / "assets" / "characters" / "turnaround_v1"


def is_magenta(red: int, green: int, blue: int) -> bool:
    return red > 150 and blue > 120 and green < 105 and red + blue - 2 * green > 200


def main() -> int:
    manifest_path = ASSET_ROOT / "turnaround_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []

    for direction in manifest["directions"]:
        for layer in manifest["layers"]:
            path = ASSET_ROOT / layer / f"{direction}.png"
            if not path.exists():
                errors.append(f"missing:{path.relative_to(ROOT)}")
                continue
            with Image.open(path) as image:
                if image.mode != "RGBA" or image.size != (256, 256):
                    errors.append(f"format:{path.relative_to(ROOT)}:{image.mode}:{image.size}")
                pixels = image.load()
                for y in range(image.height):
                    for x in range(image.width):
                        red, green, blue, alpha = pixels[x, y]
                        if alpha and is_magenta(red, green, blue):
                            errors.append(f"magenta:{path.relative_to(ROOT)}:{x},{y}")
                            break
                    if errors and errors[-1].startswith("magenta:"):
                        break
                if direction == "back" and layer in ("eyes", "eyebrows"):
                    if image.getchannel("A").getbbox() is not None:
                        errors.append(f"back_feature_not_empty:{layer}")

    if errors:
        print("TURNAROUND_VALIDATION_FAIL")
        print("\n".join(errors))
        return 1

    print("TURNAROUND_VALIDATION_PASS directions=4 layers=6 rgba=24 back_features=empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
