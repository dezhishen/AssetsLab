from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
RGS_ROOT = ROOT / "third_party/rgs_modular_animated_characters/Free 2D Animated Vector Game Character Sprites/Animated body parts"
OUTPUT = ROOT / "prototype/assets/characters/open_source/rgs_walk_reference"
PREVIEW = ROOT / "prototype/preview/assets"
TARGET_SIZE = 64
TARGET_HEIGHT = 58
BASELINE_Y = 61


def load_part(folder: str, name: str, frame: int) -> Image.Image:
    path = RGS_ROOT / folder / name / f"walk_{frame}.png"
    if not path.exists():
        raise FileNotFoundError(path)
    return Image.open(path).convert("RGBA")


def compose_frame(frame: int) -> Image.Image:
    parts = [
        load_part("Bodies", "body1", frame),
        load_part("Heads", "head3", frame),
        load_part("Eyes", "eyes7", frame),
        load_part("Left feet", "footL1", frame),
        load_part("Right feet", "footR1", frame),
        load_part("Left hands", "handL1", frame),
        load_part("Right hands", "handR1", frame),
    ]
    result = Image.new("RGBA", parts[0].size, (0, 0, 0, 0))
    for part in parts:
        result.alpha_composite(part)
    bbox = result.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"empty RGS composite frame {frame}")
    subject = result.crop(bbox)
    scale = TARGET_HEIGHT / subject.height
    subject = subject.resize((max(1, round(subject.width * scale)), TARGET_HEIGHT), Image.Resampling.LANCZOS)
    fitted = Image.new("RGBA", (TARGET_SIZE, TARGET_SIZE), (0, 0, 0, 0))
    fitted.alpha_composite(subject, ((TARGET_SIZE - subject.width) // 2, BASELINE_Y - subject.height))
    return fitted


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    frames = []
    for frame in range(8):
        image = compose_frame(frame)
        image.save(OUTPUT / f"rgs_right_frame{frame}.png")
        frames.append(image)

    sheet = Image.new("RGBA", (TARGET_SIZE * 8, TARGET_SIZE), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        sheet.alpha_composite(frame, (index * TARGET_SIZE, 0))
    sheet.save(OUTPUT / "rgs_right_walk_8.png")

    preview_frames = []
    for index, frame in enumerate(frames):
        canvas = Image.new("RGBA", (160, 160), (22, 24, 39, 255))
        canvas.alpha_composite(frame.resize((128, 128), Image.Resampling.NEAREST), (16, 0))
        ImageDraw.Draw(canvas).text((8, 140), f"FRAME {index}", fill=(235, 235, 235, 255))
        preview_frames.append(canvas)
    contact = Image.new("RGBA", (160 * 8, 160), (22, 24, 39, 255))
    for index, frame in enumerate(preview_frames):
        contact.alpha_composite(frame, (index * 160, 0))
    contact.save(PREVIEW / "rgs_walk_reference_contact.png")
    preview_frames[0].save(
        PREVIEW / "rgs_walk_reference.gif",
        save_all=True,
        append_images=preview_frames[1:],
        duration=125,
        loop=0,
        disposal=2,
    )

    manifest = {
        "schema": "open_source_walk_reference_v1",
        "source": "RGS Dev Free CC0 Modular Animated Vector Characters 2D",
        "license_file": "third_party/rgs_modular_animated_characters/Free 2D Animated Vector Game Character Sprites/License.txt",
        "direction": "right_reference",
        "frames": 8,
        "cell_size": [TARGET_SIZE, TARGET_SIZE],
        "selected_parts": ["body1", "head3", "eyes7", "footL1", "footR1", "handL1", "handR1"],
        "omitted_parts": ["mouth", "hair", "horns", "weapons"],
        "status": "verified_walk_reference_not_final_style",
        "runtime_files": [f"rgs_right_frame{frame}.png" for frame in range(8)],
    }
    (OUTPUT / "rgs_walk_reference_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("RGS_WALK_REFERENCE_PASS frames=8 parts=7 license=CC0 status=verified_walk_reference_not_final_style")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
