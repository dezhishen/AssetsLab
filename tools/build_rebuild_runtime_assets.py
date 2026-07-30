from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "prototype" / "assets" / "characters" / "rebuild_atlas_v1"
OUTPUT = ROOT / "prototype" / "assets" / "characters" / "rebuild_atlas_v1_runtime" / "male"
CALIBRATION_PATH = ROOT / "prototype" / "preview" / "calibration" / "latest.json"
BODY_CALIBRATION_PATH = ROOT / "prototype" / "preview" / "calibration" / "body_latest.json"
DIRECTIONS = ("front", "right", "back", "left")
LAYERS = ("face_base", "face", "ears")
CELL_SIZE = 64
FRAMES_PER_DIRECTION = 8
TARGET_FRAME_HEIGHT = 34
TARGET_BASELINE_Y = 34

# All detachable parts are registered against explicit 64 x 64 head anchors.
# These are the only art-placement values a future hair/clothing layer needs
# to consume; no direction-specific opaque translation table is used.
DEFAULT_ANCHOR_TARGETS = {
    "front": {
        "face_center": (31, 19),
        "ear_left": (15, 22),
        "ear_right": (49, 22),
    },
    "right": {
        "face_center": (40, 16),
        "ear": (27, 23),
    },
    "back": {
        "ear_left": (16, 17),
        "ear_right": (48, 17),
    },
    "left": {
        "face_center": (30, 20),
        "ear": (41, 23),
    },
}

FEATURE_SOURCE_DIRECTION = {
    "front": "front",
    "right": "left",
    "back": "back",
    "left": "right",
}


def body_anchor_offsets() -> tuple[dict[str, tuple[int, int]], dict | None]:
    offsets = {direction: (0, 0) for direction in DIRECTIONS}
    if not BODY_CALIBRATION_PATH.exists():
        return offsets, None
    payload = json.loads(BODY_CALIBRATION_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "body_anchor_calibration_v1":
        raise ValueError(f"unsupported body calibration schema: {payload.get('schema')}")
    for direction in DIRECTIONS:
        value = payload.get("calibration", {}).get(direction, {})
        offsets[direction] = (round(value.get("x", 0)), round(value.get("y", 0)))
    return offsets, payload


def layer_image(direction: str, layer: str) -> Image.Image:
    source_direction = FEATURE_SOURCE_DIRECTION[direction] if layer in ("face", "ears") else direction
    if layer == "face":
        eyes = Image.open(SOURCE / "eyes" / f"{source_direction}.png").convert("RGBA")
        eyebrows = Image.open(SOURCE / "eyebrows" / f"{source_direction}.png").convert("RGBA")
        image = Image.new("RGBA", eyes.size, (0, 0, 0, 0))
        image.alpha_composite(eyes)
        image.alpha_composite(eyebrows)
        return image
    return Image.open(SOURCE / layer / f"{source_direction}.png").convert("RGBA")


def union_bbox(images: list[Image.Image]) -> tuple[int, int, int, int]:
    result = None
    for image in images:
        bbox = image.getchannel("A").getbbox()
        if bbox is None:
            continue
        result = bbox if result is None else (
            min(result[0], bbox[0]),
            min(result[1], bbox[1]),
            max(result[2], bbox[2]),
            max(result[3], bbox[3]),
        )
    if result is None:
        raise ValueError("empty runtime frame")
    return result


def fit_to_runtime(image: Image.Image, frame_bbox: tuple[int, int, int, int]) -> Image.Image:
    crop = image.crop(frame_bbox)
    scale = TARGET_FRAME_HEIGHT / (frame_bbox[3] - frame_bbox[1])
    width = max(1, round(crop.width * scale))
    crop = crop.resize((width, TARGET_FRAME_HEIGHT), Image.Resampling.LANCZOS)
    # Resampling transparent raster art creates tiny colored alpha pixels
    # outside the contour. They become a visible noisy halo in the GIF and
    # in Godot's nearest-neighbour preview, so remove only the near-zero
    # fringe and keep the solid contour intact.
    pixels = crop.load()
    for y in range(crop.height):
        for x in range(crop.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha < 32:
                pixels[x, y] = (red, green, blue, 0)
    output = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    output.alpha_composite(crop, ((CELL_SIZE - width) // 2, TARGET_BASELINE_Y - TARGET_FRAME_HEIGHT))
    return output


def shift_image(image: Image.Image, dx: int, dy: int) -> Image.Image:
    shifted = Image.new("RGBA", image.size, (0, 0, 0, 0))
    source_box = (
        max(0, -dx),
        max(0, -dy),
        min(image.width, image.width - dx),
        min(image.height, image.height - dy),
    )
    target = (max(0, dx), max(0, dy))
    if source_box[2] > source_box[0] and source_box[3] > source_box[1]:
        shifted.alpha_composite(image.crop(source_box), target)
    return shifted


def part_for_region(image: Image.Image, region: tuple[int, int, int, int]) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rectangle(region, fill=255)
    part = Image.new("RGBA", image.size, (0, 0, 0, 0))
    part.paste(image, (0, 0), mask)
    return part


def alpha_center(image: Image.Image) -> tuple[float, float] | None:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return None
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def align_to_anchor(image: Image.Image, target: tuple[int, int]) -> tuple[Image.Image, dict]:
    current = alpha_center(image)
    if current is None:
        return image, {"target": target, "source": None, "shift": (0, 0)}
    shift = (round(target[0] - current[0]), round(target[1] - current[1]))
    return shift_image(image, shift[0], shift[1]), {
        "target": target,
        "source": current,
        "shift": shift,
    }


def align_ear_pair(image: Image.Image, left_target: tuple[int, int], right_target: tuple[int, int]) -> tuple[Image.Image, dict]:
    midpoint = image.width // 2
    left = part_for_region(image, (0, 0, midpoint - 1, image.height - 1))
    right = part_for_region(image, (midpoint, 0, image.width - 1, image.height - 1))
    left_current = alpha_center(left)
    right_current = alpha_center(right)
    left_shift = (0, 0) if left_current is None else (round(left_target[0] - left_current[0]), round(left_target[1] - left_current[1]))
    right_shift = (0, 0) if right_current is None else (round(right_target[0] - right_current[0]), round(right_target[1] - right_current[1]))
    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    result.alpha_composite(shift_image(left, left_shift[0], left_shift[1]))
    result.alpha_composite(shift_image(right, right_shift[0], right_shift[1]))
    return result, {
        "left": {"target": left_target, "source": left_current, "shift": left_shift},
        "right": {"target": right_target, "source": right_current, "shift": right_shift},
    }


def head_anchors(base: Image.Image) -> dict:
    bbox = base.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("empty head base")
    return {
        "bbox": bbox,
        "center": ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2),
        "left_edge": (bbox[0], (bbox[1] + bbox[3]) / 2),
        "right_edge": (bbox[2], (bbox[1] + bbox[3]) / 2),
        "top": ((bbox[0] + bbox[2]) / 2, bbox[1]),
        "neck": ((bbox[0] + bbox[2]) / 2, bbox[3]),
    }


def calibrated_anchor_targets() -> tuple[dict[str, dict[str, tuple[int, int]]], dict | None]:
    targets = {
        direction: {key: tuple(value) for key, value in values.items()}
        for direction, values in DEFAULT_ANCHOR_TARGETS.items()
    }
    if not CALIBRATION_PATH.exists():
        return targets, None
    payload = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != "component_anchor_calibration_v1":
        raise ValueError(f"unsupported calibration schema: {payload.get('schema')}")
    calibration = payload.get("calibration", {})
    for direction in ("front", "right", "back", "left"):
        values = calibration.get(direction, {})
        if "face_center" in targets[direction] and "face" in values:
            delta = values.get("face", {})
            target = targets[direction]["face_center"]
            targets[direction]["face_center"] = (target[0] + round(delta.get("x", 0)), target[1] + round(delta.get("y", 0)))
        if direction in ("front", "back"):
            for key in ("ear_left", "ear_right"):
                delta = values.get(key, {})
                target = targets[direction][key]
                targets[direction][key] = (target[0] + round(delta.get("x", 0)), target[1] + round(delta.get("y", 0)))
        else:
            delta = values.get("ear", {})
            target = targets[direction]["ear"]
            targets[direction]["ear"] = (target[0] + round(delta.get("x", 0)), target[1] + round(delta.get("y", 0)))

    # Enforce the user's left/right mirror standard. The pair is averaged in
    # mirrored space, so a small manual marking error on either side does not
    # become a permanent directional asymmetry.
    mirror_center_x = 32
    for key in ("face_center", "ear"):
        right = targets["right"][key]
        left = targets["left"][key]
        right_from_left = (2 * mirror_center_x - left[0], left[1])
        right_x = round((right[0] + right_from_left[0]) / 2)
        y = round((right[1] + left[1]) / 2)
        targets["right"][key] = (right_x, y)
        targets["left"][key] = (2 * mirror_center_x - right_x, y)
    return targets, payload


def prepare_direction(direction: str, anchor_targets: dict[str, dict[str, tuple[int, int]]]) -> tuple[dict[str, Image.Image], dict]:
    source_layers = {layer: layer_image(direction, layer) for layer in LAYERS}
    frame_bbox = union_bbox(list(source_layers.values()))
    fitted = {layer: fit_to_runtime(image, frame_bbox) for layer, image in source_layers.items()}
    anchors = head_anchors(fitted["face_base"])
    targets = dict(anchor_targets[direction])
    if direction == "front":
        # Front ears should straddle the head contour, not float beside it.
        # Keep a small overlap with the contour so the ear remains visibly
        # attached after nearest-neighbour scaling and compositing.
        head_left, _, head_right, _ = anchors["bbox"]
        if "ear_left" in targets:
            targets["ear_left"] = (head_left + 2, targets["ear_left"][1])
        if "ear_right" in targets:
            targets["ear_right"] = (head_right - 2, targets["ear_right"][1])
    applied = {}

    if "face_center" in targets:
        fitted["face"], applied["face"] = align_to_anchor(fitted["face"], targets["face_center"])
    if "ear_left" in targets and "ear_right" in targets:
        fitted["ears"], applied["ears"] = align_ear_pair(fitted["ears"], targets["ear_left"], targets["ear_right"])
    elif "ear" in targets:
        fitted["ears"], applied["ears"] = align_to_anchor(fitted["ears"], targets["ear"])

    return fitted, {
        "head": anchors,
        "targets": targets,
        "applied": applied,
        "frame_bbox": frame_bbox,
    }


def build_sheet(layer: str, prepared: dict[str, dict[str, Image.Image]]) -> Path:
    sheet = Image.new("RGBA", (CELL_SIZE * FRAMES_PER_DIRECTION, CELL_SIZE * len(DIRECTIONS)), (0, 0, 0, 0))
    frame_dir = OUTPUT / f"{layer}_frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    for row, direction in enumerate(DIRECTIONS):
        image = prepared[direction][layer]
        for frame in range(FRAMES_PER_DIRECTION):
            image.save(frame_dir / f"walk_row{row}_frame{frame}.png")
            sheet.alpha_composite(image, (frame * CELL_SIZE, row * CELL_SIZE))
    path = OUTPUT / f"{layer}_walk_4way.png"
    sheet.save(path)
    return path


def main() -> int:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    anchor_targets, calibration_payload = calibrated_anchor_targets()
    head_body_offsets, body_calibration_payload = body_anchor_offsets()
    prepared: dict[str, dict[str, Image.Image]] = {}
    registrations: dict[str, dict] = {}
    for direction in DIRECTIONS:
        prepared[direction], registrations[direction] = prepare_direction(direction, anchor_targets)

    manifest = {
        "generator": "build_rebuild_runtime_assets.py",
        "generator_version": 2,
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "directions": list(DIRECTIONS),
        "frames_per_direction": FRAMES_PER_DIRECTION,
        "cell_size": [CELL_SIZE, CELL_SIZE],
        "target_frame_height": TARGET_FRAME_HEIGHT,
        "target_baseline_y": TARGET_BASELINE_Y,
        "anchor_schema": "head_contour_anchors_v1",
        "anchor_space": "runtime_64x64",
        "anchor_targets": anchor_targets,
        "calibration_source": CALIBRATION_PATH.relative_to(ROOT).as_posix() if calibration_payload is not None else None,
        "body_calibration_source": BODY_CALIBRATION_PATH.relative_to(ROOT).as_posix() if body_calibration_payload is not None else None,
        "body_anchor_offsets": {direction: list(head_body_offsets[direction]) for direction in DIRECTIONS},
        "mirror_policy": "right_left_anchor_average_around_x32",
        "feature_source_direction": FEATURE_SOURCE_DIRECTION,
        "registrations": registrations,
        "layers": list(LAYERS),
        "hair_included": False,
        "notes": "Every detachable layer is positioned from explicit head-contour anchors. Face and ear layers use the 2/4 source exchange without implicit mirroring.",
        "files": {},
    }
    for layer in LAYERS:
        manifest["files"][layer] = build_sheet(layer, prepared).relative_to(ROOT).as_posix()
    (OUTPUT / "runtime_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("REBUILD_RUNTIME_ASSET_PASS directions=4 layers=3 frames=32 anchors=head_contour_anchors_v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
