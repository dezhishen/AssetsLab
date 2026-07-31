"""Validate the alternating side-walk leg occlusion contract."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "prototype/assets/characters/limb_puzzle.json"
EXPECTED = [
    "right_foot",
    "right_foot",
    "right_foot",
    "left_foot",
    "left_foot",
    "left_foot",
    "left_foot",
    "right_foot",
]


def main() -> int:
    payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    policy = payload.get("foot_occlusion_policy", {}).get("front_leg_by_frame")
    if policy != EXPECTED:
        raise SystemExit(f"unexpected foot policy: {policy!r}")

    actual: list[str] = []
    for index, frame in enumerate(payload.get("frames", [])):
        parts = frame.get("parts", {})
        left = parts.get("left_foot", {}).get("z_order")
        right = parts.get("right_foot", {}).get("z_order")
        if left == right:
            raise SystemExit(f"frame {index} has equal foot z-order")
        actual.append("left_foot" if left > right else "right_foot")
    if actual != EXPECTED:
        raise SystemExit(f"z-order does not match policy: {actual!r}")
    print("LIMB_OCCLUSION_VALIDATION_PASS frames=8 transitions=after_frame3_after_frame7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
