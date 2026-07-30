from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "prototype" / "assets" / "characters" / "rebuild_atlas_v1_runtime" / "male"
TOLERANCE = 1.5


def center(image: Image.Image) -> tuple[float, float] | None:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return None
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def frame(path: Path, row: int) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    return image.crop((0, row * 64, 64, row * 64 + 64))


def check(actual: tuple[float, float] | None, expected: list[int] | tuple[int, int], label: str) -> None:
    if actual is None:
        raise ValueError(f"missing anchor: {label}")
    if abs(actual[0] - expected[0]) > TOLERANCE or abs(actual[1] - expected[1]) > TOLERANCE:
        raise ValueError(f"anchor drift {label}: actual={actual} expected={expected}")


def main() -> int:
    manifest = json.loads((RUNTIME / "runtime_manifest.json").read_text(encoding="utf-8"))
    # Registrations contain the effective targets after structural rules such
    # as keeping front ears outside the head contour have been applied.
    targets = {
        direction: registration["targets"]
        for direction, registration in manifest["registrations"].items()
    }
    for row, direction in enumerate(manifest["directions"]):
        face = frame(RUNTIME / "face_walk_4way.png", row)
        ears = frame(RUNTIME / "ears_walk_4way.png", row)
        direction_targets = targets[direction]
        if "face_center" in direction_targets:
            check(center(face), direction_targets["face_center"], f"{direction}.face_center")
        if "ear" in direction_targets:
            check(center(ears), direction_targets["ear"], f"{direction}.ear")
        else:
            left = ears.crop((0, 0, 32, 64))
            right = ears.crop((32, 0, 64, 64))
            check(center(left), direction_targets["ear_left"], f"{direction}.ear_left")
            right_center = center(right)
            if right_center is not None:
                right_center = (right_center[0] + 32, right_center[1])
            check(right_center, direction_targets["ear_right"], f"{direction}.ear_right")
    print(f"REBUILD_RUNTIME_ANCHOR_VALIDATION_PASS directions={len(manifest['directions'])} tolerance={TOLERANCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
