from __future__ import annotations

import base64
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "prototype/preview/body_outline_split_v2_manual.project.json"
OUTPUT = ROOT / "prototype/assets/characters/generated/body_outline_split_v2_manual_from_project.png"
FRAME_OUTPUT = ROOT / "prototype/assets/characters/generated/body_outline_split_v2_manual_from_project"
PREVIEW = ROOT / "prototype/preview/assets/body_outline_split_v2_manual_from_project_contact.png"
GIF = ROOT / "prototype/preview/assets/body_outline_split_v2_manual_from_project.gif"
MANIFEST = ROOT / "prototype/assets/characters/generated/body_outline_split_v2_manual_from_project_manifest.json"


def load_project() -> tuple[dict, list[Image.Image]]:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    if payload.get("schema") != "body_outline_pixel_project_v1":
        raise ValueError("unexpected pixel project schema")
    width = int(payload.get("width", 0))
    height = int(payload.get("height", 0))
    frame_count = int(payload.get("frame_count", 0))
    encoded_frames = payload.get("frames_rgba_base64")
    if width != 64 or height != 64 or frame_count != 8 or not isinstance(encoded_frames, list):
        raise ValueError("expected an 8-frame 64x64 RGBA project")
    if len(encoded_frames) != frame_count:
        raise ValueError("frame_count does not match frames_rgba_base64")

    frames: list[Image.Image] = []
    expected_size = width * height * 4
    for index, encoded in enumerate(encoded_frames):
        raw = base64.b64decode(encoded)
        if len(raw) != expected_size:
            raise ValueError(f"frame {index} has {len(raw)} bytes, expected {expected_size}")
        frames.append(Image.frombytes("RGBA", (width, height), raw))
    return payload, frames


def main() -> int:
    payload, frames = load_project()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    FRAME_OUTPUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)

    sheet = Image.new("RGBA", (64 * len(frames), 64), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        frame.save(FRAME_OUTPUT / f"frame{index}.png")
        sheet.alpha_composite(frame, (index * 64, 0))
    sheet.save(OUTPUT)

    scale = 6
    contact = Image.new("RGBA", (64 * scale * len(frames), 64 * scale + 22), (22, 24, 39, 255))
    draw = ImageDraw.Draw(contact)
    for index, frame in enumerate(frames):
        contact.alpha_composite(frame.resize((64 * scale, 64 * scale), Image.Resampling.NEAREST), (index * 64 * scale, 0))
        draw.text((index * 64 * scale + 4, 64 * scale + 4), f"F{index}", fill=(240, 240, 240, 255), font=ImageFont.load_default())
    contact.save(PREVIEW)

    gif_frames = [frame.resize((256, 256), Image.Resampling.NEAREST) for frame in frames]
    gif_frames[0].save(GIF, save_all=True, append_images=gif_frames[1:], duration=125, loop=0, disposal=2)

    manifest = {
        "schema": "body_outline_pixel_project_processed_v1",
        "source_project": SOURCE.relative_to(ROOT).as_posix(),
        "source_schema": payload["schema"],
        "cell_size": [64, 64],
        "frames": 8,
        "sheet": OUTPUT.relative_to(ROOT).as_posix(),
        "frame_directory": FRAME_OUTPUT.relative_to(ROOT).as_posix(),
        "limb_motion_reference": "prototype/assets/characters/limb_puzzle.json",
        "notes": "Pixel project JSON is authoritative for artwork; limb_puzzle_v1 remains authoritative for limb pose and z_order.",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"BODY_PIXEL_PROJECT_PASS frames={len(frames)} sheet={OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
