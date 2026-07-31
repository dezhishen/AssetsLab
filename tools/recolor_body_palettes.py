"""Create skin-tone variants while preserving body frame geometry and alpha."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "prototype/assets/characters/generated/female_adventurer_reference_mannequin_v1_adapted/body_frames"
DEFAULT_OUTPUT = ROOT / "prototype/assets/characters/generated/female_adventurer_reference_mannequin_v1_adapted/skin_palette_variants_v1"

PALETTES = {
    "light": {
        "outline": (104, 74, 62),
        "shadow": (213, 157, 124),
        "base": (244, 211, 164),
        "highlight": (255, 236, 201),
    },
    "warm": {
        "outline": (94, 60, 48),
        "shadow": (193, 122, 88),
        "base": (231, 166, 113),
        "highlight": (255, 210, 161),
    },
    "deep": {
        "outline": (55, 38, 34),
        "shadow": (132, 79, 61),
        "base": (181, 112, 79),
        "highlight": (220, 159, 114),
    },
}


def semantic_tone(rgb: tuple[int, int, int]) -> str:
    luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    maximum = max(rgb)
    if maximum < 105:
        return "outline"
    if luminance < 178:
        return "shadow"
    if luminance > 236:
        return "highlight"
    return "base"


def alpha_digest(image: Image.Image) -> str:
    return hashlib.sha256(image.getchannel("A").tobytes()).hexdigest()


def recolor(image: Image.Image, palette: dict[str, tuple[int, int, int]]) -> Image.Image:
    source = image.convert("RGBA")
    output = Image.new("RGBA", source.size)
    pixels = []
    for r, g, b, a in source.getdata():
        if a == 0:
            pixels.append((0, 0, 0, 0))
            continue
        tone = semantic_tone((r, g, b))
        nr, ng, nb = palette[tone]
        pixels.append((nr, ng, nb, a))
    output.putdata(pixels)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    source = args.source if args.source.is_absolute() else ROOT / args.source
    output = args.output if args.output.is_absolute() else ROOT / args.output
    frames = sorted(source.glob("walk_row*_frame*.png"))
    if len(frames) != 32:
        raise ValueError(f"expected 32 authoritative body frames, found {len(frames)}")

    records: list[dict[str, object]] = []
    for palette_name, palette in PALETTES.items():
        palette_dir = output / palette_name / "body_frames"
        palette_dir.mkdir(parents=True, exist_ok=True)
        for frame_path in frames:
            before = Image.open(frame_path).convert("RGBA")
            after = recolor(before, palette)
            if before.size != after.size or alpha_digest(before) != alpha_digest(after):
                raise AssertionError(f"geometry/alpha changed for {palette_name}/{frame_path.name}")
            destination = palette_dir / frame_path.name
            after.save(destination)
        records.append({"name": palette_name, "colors": palette})

    manifest = {
        "schema": "skin_palette_variants_v1",
        "status": "preview_pipeline_only",
        "source": str(source.relative_to(ROOT)).replace("\\", "/"),
        "preservation": {
            "frame_count": 32,
            "canvas": [64, 64],
            "alpha_and_coordinates": "validated identical for every output frame",
            "method": "semantic tone remap only; no resize, crop, mirror, or geometry edit",
        },
        "palettes": records,
        "runtime_policy": "not wired into the player until appearance selection is specified",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"BODY_PALETTE_PASS palettes={len(PALETTES)} frames_per_palette=32 output={output}")


if __name__ == "__main__":
    main()
