from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "prototype" / "assets" / "characters" / "rebuild_atlas_v1_runtime" / "male"
BODY_SOURCE = ROOT / "prototype" / "assets" / "characters" / "rebuild_body_v2"
BODY_CANDIDATE_SOURCE = ROOT / "prototype" / "assets" / "characters" / "rebuild_body_v5_rgs"
BODY_BOMBO_CANDIDATE_SOURCE = ROOT / "prototype" / "assets" / "characters" / "rebuild_body_v6_bombo"
BODY_OUTLINE_SOURCES = (
    ROOT / "prototype" / "assets" / "characters" / "generated" / "body_outline_split_v1_right_walk_8.png",
    ROOT / "prototype" / "assets" / "characters" / "generated" / "body_outline_split_v2_right_walk_8.png",
)
OUTPUT = ROOT / "prototype" / "preview" / "assets"
RUNTIME_OUTPUT = OUTPUT / "runtime"
BODY_CALIBRATION_PATH = ROOT / "prototype" / "preview" / "calibration" / "body_latest.json"
DIRECTIONS = ("front", "right", "back", "left")
BODY_LAYERS = ("feet", "lower_body", "arms", "torso")


def frame(sheet: Image.Image, row: int, column: int = 0) -> Image.Image:
    return sheet.crop((column * 64, row * 64, column * 64 + 64, row * 64 + 64))


def build_body_frame(body_sheets: dict[str, Image.Image], row: int, column: int) -> Image.Image:
    result = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for layer in BODY_LAYERS:
        result.alpha_composite(frame(body_sheets[layer], row, column))
    return result


def build_character_frame(
    body_sheets: dict[str, Image.Image],
    head_sheets: dict[str, Image.Image],
    row: int,
    column: int,
    head_offset: tuple[int, int] = (0, 0),
) -> Image.Image:
    result = build_body_frame(body_sheets, row, column)
    # Head base and detachable layers use the same 64x64 runtime registration
    # as the body.  Keeping these as separate source layers preserves future
    # clothing and hair insertion points even though this preview is flattened.
    for layer in ("face_base", "ears", "face"):
        result.alpha_composite(frame(head_sheets[layer], row, column), head_offset)
    return result


def load_body_offsets() -> dict[str, tuple[int, int]]:
    offsets = {direction: (0, 0) for direction in DIRECTIONS}
    if not BODY_CALIBRATION_PATH.exists():
        return offsets
    payload = json.loads(BODY_CALIBRATION_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "body_anchor_calibration_v1":
        raise ValueError(f"unsupported body calibration schema: {payload.get('schema')}")
    for direction in DIRECTIONS:
        value = payload.get("calibration", {}).get(direction, {})
        offsets[direction] = (round(value.get("x", 0)), round(value.get("y", 0)))
    return offsets


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    RUNTIME_OUTPUT.mkdir(parents=True, exist_ok=True)
    for outline_source in BODY_OUTLINE_SOURCES:
        if outline_source.exists():
            shutil.copy2(outline_source, OUTPUT / outline_source.name)
    for preview_artifact in (
        "movement_rgs_body_candidate.gif",
        "movement_rgs_body_candidate_contact.png",
        "movement_bombo_body_candidate.gif",
        "movement_bombo_body_candidate_contact.png",
    ):
        artifact_path = ROOT / "prototype" / "test_output" / preview_artifact
        if artifact_path.exists():
            shutil.copy2(artifact_path, OUTPUT / preview_artifact)
    for filename in ("face_base_walk_4way.png", "face_walk_4way.png", "ears_walk_4way.png", "runtime_manifest.json"):
        shutil.copy2(SOURCE / filename, RUNTIME_OUTPUT / filename)
    for layer in BODY_LAYERS:
        shutil.copy2(BODY_SOURCE / f"{layer}_walk_4way.png", RUNTIME_OUTPUT / f"{layer}_walk_4way.png")
        candidate_layer = BODY_CANDIDATE_SOURCE / layer
        candidate_output = OUTPUT / "body_candidate_v5" / layer
        if candidate_layer.exists():
            candidate_output.mkdir(parents=True, exist_ok=True)
            for frame in range(8):
                shutil.copy2(candidate_layer / f"right_frame{frame}.png", candidate_output / f"right_frame{frame}.png")
        bombo_layer = BODY_BOMBO_CANDIDATE_SOURCE / layer
        bombo_output = OUTPUT / "body_candidate_v6" / layer
        if bombo_layer.exists():
            bombo_output.mkdir(parents=True, exist_ok=True)
            for frame in range(8):
                shutil.copy2(bombo_layer / f"right_frame{frame}.png", bombo_output / f"right_frame{frame}.png")
    body_offsets = load_body_offsets()
    manifest = json.loads((SOURCE / "runtime_manifest.json").read_text(encoding="utf-8"))
    debug = Image.new("RGBA", (1024, 256), (22, 24, 39, 255))
    base_sheet = Image.open(SOURCE / "face_base_walk_4way.png").convert("RGBA")
    ears_sheet = Image.open(SOURCE / "ears_walk_4way.png").convert("RGBA")
    face_sheet = Image.open(SOURCE / "face_walk_4way.png").convert("RGBA")
    body_sheets = {
        layer: Image.open(BODY_SOURCE / f"{layer}_walk_4way.png").convert("RGBA")
        for layer in BODY_LAYERS
    }
    head_sheets = {
        layer: Image.open(SOURCE / f"{layer}_walk_4way.png").convert("RGBA")
        for layer in ("face_base", "ears", "face")
    }
    character_sheet = Image.new("RGBA", (512, 256), (0, 0, 0, 0))
    body_sheet = Image.new("RGBA", (512, 256), (0, 0, 0, 0))
    for row in range(4):
        direction = DIRECTIONS[row]
        for column in range(8):
            body_sheet.alpha_composite(build_body_frame(body_sheets, row, column), (column * 64, row * 64))
            character_sheet.alpha_composite(build_character_frame(body_sheets, head_sheets, row, column, body_offsets[direction]), (column * 64, row * 64))

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

        body_preview = build_body_frame(body_sheets, row, 0).resize((512, 512), Image.Resampling.NEAREST)
        character_preview = build_character_frame(body_sheets, head_sheets, row, 0, body_offsets[direction]).resize((512, 512), Image.Resampling.NEAREST)
        ImageDraw.Draw(body_preview).text((18, 18), f"{direction} body", fill=(242, 241, 238, 255), font=ImageFont.load_default())
        ImageDraw.Draw(character_preview).text((18, 18), f"{direction} full", fill=(242, 241, 238, 255), font=ImageFont.load_default())
        body_preview.save(OUTPUT / f"body_{direction}.png")
        character_preview.save(OUTPUT / f"character_{direction}.png")

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
    body_sheet.save(OUTPUT / "body_walk_4way.png")
    character_sheet.save(OUTPUT / "character_walk_4way.png")
    gif_frames = [
        build_character_frame(body_sheets, head_sheets, row, column, body_offsets[DIRECTIONS[row]]).resize((256, 256), Image.Resampling.NEAREST)
        for row in range(4)
        for column in range(8)
    ]
    gif_frames[0].save(
        OUTPUT / "character_walk_4way.gif",
        save_all=True,
        append_images=gif_frames[1:],
        duration=100,
        loop=0,
        disposal=2,
        transparency=0,
    )
    print("PREVIEW_ASSETS_PASS directions=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
