from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "prototype/assets/characters/generated/walk_body_bombo_reference_v6_source.png"
OUTPUT = ROOT / "prototype/assets/characters/rebuild_body_v6_bombo"
PREVIEW = ROOT / "prototype/preview/assets"
CELL_SIZE = 64
SOURCE_FRAME_COUNT = 8
FRAME_COUNT = 8
TARGET_BODY_HEIGHT = 30
BASELINE_Y = 58


def alpha_mask(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    mask = Image.new("L", rgba.size, 0)
    source_pixels = rgba.load()
    mask_pixels = mask.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, alpha = source_pixels[x, y]
            # The image generator returned a neutral checkerboard instead of
            # alpha. Character pixels have a warm hue, while the checkerboard
            # has nearly equal RGB channels.
            if alpha >= 32 and max(red, green, blue) - min(red, green, blue) >= 10:
                mask_pixels[x, y] = 255
    return mask


def crop_frame(source: Image.Image, frame: int) -> Image.Image:
    left = round(frame * source.width / SOURCE_FRAME_COUNT)
    right = round((frame + 1) * source.width / SOURCE_FRAME_COUNT)
    return source.crop((left, 0, right, source.height))


def fit_frame(frame: Image.Image) -> Image.Image:
    mask = alpha_mask(frame)
    bbox = mask.getbbox()
    if bbox is None:
        raise ValueError("empty body frame")
    crop = frame.crop(bbox).convert("RGBA")
    crop_mask = mask.crop(bbox)
    scale = TARGET_BODY_HEIGHT / crop.height
    width = max(1, round(crop.width * scale))
    crop = crop.resize((width, TARGET_BODY_HEIGHT), Image.Resampling.LANCZOS)
    crop_mask = crop_mask.resize((width, TARGET_BODY_HEIGHT), Image.Resampling.LANCZOS)
    crop.putalpha(crop_mask.point(lambda value: 255 if value >= 32 else value))
    result = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    result.alpha_composite(crop, ((CELL_SIZE - width) // 2, BASELINE_Y - TARGET_BODY_HEIGHT))
    return result


def restrict(mask: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    region = Image.new("L", mask.size, 0)
    ImageDraw.Draw(region).rectangle(box, fill=255)
    return ImageChops.multiply(mask, region)


def split_layers(body: Image.Image) -> dict[str, Image.Image]:
    mask = alpha_mask(body)
    body_rgb = body.convert("RGB")
    layers: dict[str, Image.Image] = {}
    regions = {
        "torso": (0, 0, CELL_SIZE - 1, 47),
        "arms": (0, 32, CELL_SIZE - 1, 55),
        "lower_body": (0, 43, CELL_SIZE - 1, CELL_SIZE - 1),
        "feet": (0, 53, CELL_SIZE - 1, CELL_SIZE - 1),
    }
    for layer, region in regions.items():
        part = Image.new("RGBA", body.size, (0, 0, 0, 0))
        part.putalpha(restrict(mask, region))
        part.paste(body_rgb, (0, 0), part.getchannel("A"))
        layers[layer] = part
    layers["body_base"] = body
    return layers


def main() -> int:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    source = Image.open(SOURCE).convert("RGBA")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    phase_frames = [fit_frame(crop_frame(source, frame)) for frame in range(SOURCE_FRAME_COUNT)]
    layers_by_name: dict[str, list[Image.Image]] = {name: [] for name in ("torso", "arms", "lower_body", "feet", "body_base")}
    for body in phase_frames:
        for name, image in split_layers(body).items():
            layers_by_name[name].append(image)

    for layer, layer_frames in layers_by_name.items():
        layer_dir = OUTPUT / layer
        layer_dir.mkdir(parents=True, exist_ok=True)
        sheet = Image.new("RGBA", (CELL_SIZE * FRAME_COUNT, CELL_SIZE), (0, 0, 0, 0))
        for frame, image in enumerate(layer_frames):
            image.save(layer_dir / f"right_frame{frame}.png")
            sheet.alpha_composite(image, (frame * CELL_SIZE, 0))
        sheet.save(layer_dir / "right_walk_8.png")

    contact = Image.new("RGBA", (CELL_SIZE * FRAME_COUNT, CELL_SIZE), (22, 24, 39, 255))
    for frame, image in enumerate(phase_frames):
        contact.alpha_composite(image, (frame * CELL_SIZE, 0))
    contact.resize((CELL_SIZE * FRAME_COUNT * 4, CELL_SIZE * 4), Image.Resampling.NEAREST).save(
        PREVIEW / "rebuild_body_v6_bombo_right_contact.png"
    )

    manifest = {
        "schema": "rebuild_body_v6_bombo_pose_reference",
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "direction": "right",
        "cell_size": [CELL_SIZE, CELL_SIZE],
        "frames": FRAME_COUNT,
        "target_body_height": TARGET_BODY_HEIGHT,
        "baseline_y": BASELINE_Y,
        "status": "candidate_requires_visual_review",
        "motion_contract": {
            "neutral_frames": [0, 4],
            "first_step_after_neutral": "viewer_right_leg",
            "both_arms_participate": True,
            "opposite_arm_swing": True,
        },
        "layers": ["torso", "arms", "lower_body", "feet", "body_base"],
    }
    (OUTPUT / "rebuild_body_v6_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("WALK_BODY_CANDIDATE_PASS direction=right frames=8 layers=5 status=candidate_requires_visual_review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
