from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "prototype" / "assets" / "characters" / "rebuild_atlas_v1_runtime" / "male"
OUTPUT = ROOT / "prototype" / "preview" / "assets"
RUNTIME_OUTPUT = OUTPUT / "runtime"
DIRECTIONS = ("front", "right", "back", "left")


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    RUNTIME_OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename in ("face_base_walk_4way.png", "face_walk_4way.png", "ears_walk_4way.png", "runtime_manifest.json"):
        shutil.copy2(SOURCE / filename, RUNTIME_OUTPUT / filename)
    manifest = json.loads((SOURCE / "runtime_manifest.json").read_text(encoding="utf-8"))
    debug = Image.new("RGBA", (1024, 256), (22, 24, 39, 255))
    base_sheet = Image.open(SOURCE / "face_base_walk_4way.png").convert("RGBA")
    ears_sheet = Image.open(SOURCE / "ears_walk_4way.png").convert("RGBA")
    face_sheet = Image.open(SOURCE / "face_walk_4way.png").convert("RGBA")
    for direction in DIRECTIONS:
        canvas = Image.new("RGBA", (512, 512), (22, 24, 39, 255))
        row = DIRECTIONS.index(direction)
        frame_box = (0, row * 64, 64, row * 64 + 64)
        base = base_sheet.crop(frame_box).resize((512, 512), Image.Resampling.NEAREST)
        ears = ears_sheet.crop(frame_box).resize((512, 512), Image.Resampling.NEAREST)
        face = face_sheet.crop(frame_box).resize((512, 512), Image.Resampling.NEAREST)
        canvas.alpha_composite(base)
        canvas.alpha_composite(ears)
        canvas.alpha_composite(face)
        ImageDraw.Draw(canvas).text((18, 18), direction, fill=(242, 241, 238, 255), font=ImageFont.load_default())
        canvas.save(OUTPUT / f"rebuild_{direction}.png")

        debug.alpha_composite(canvas.resize((256, 256), Image.Resampling.NEAREST), (row * 256, 0))
        debug_draw = ImageDraw.Draw(debug)
        registration = manifest["registrations"][direction]
        debug_draw.rectangle(tuple(value * 4 for value in registration["head"]["bbox"]), outline=(91, 220, 255, 255), width=2)
        targets = registration["targets"]
        marker_targets = []
        for key in ("face_center", "ear_left", "ear_right", "ear"):
            if key in targets:
                marker_targets.append((key, targets[key]))
        for key, (x, y) in marker_targets:
            color = (255, 83, 190, 255) if key == "face_center" else (255, 213, 77, 255)
            center_x = row * 256 + x * 4
            center_y = y * 4
            debug_draw.ellipse((center_x - 5, center_y - 5, center_x + 5, center_y + 5), outline=color, width=2)
        debug_draw.text((row * 256 + 8, 8), direction, fill=(242, 241, 238, 255), font=ImageFont.load_default())
    debug.save(OUTPUT / "anchor_debug.png")
    print("PREVIEW_ASSETS_PASS directions=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
