from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
BASE_SOURCE = ROOT / "prototype" / "assets" / "characters" / "generated" / "neutral_face_base_rebuild_v1_male.png"
FEATURE_SOURCE = ROOT / "prototype" / "assets" / "characters" / "generated" / "facial_feature_atlas_rebuild_v1_male.png"
OUTPUT = ROOT / "prototype" / "assets" / "characters" / "rebuild_atlas_v1"
DIRECTIONS = ("front", "right", "back", "left")
CELL_SIZE = 256
TARGET_HEIGHT = 220
BASELINE_Y = 238


def is_magenta(red: int, green: int, blue: int) -> bool:
    return red > 150 and blue > 120 and green < 105 and red + blue - 2 * green > 200


def foreground_mask(image: Image.Image) -> Image.Image:
    return image.getchannel("A").point(lambda value: 255 if value >= 16 else 0)


def color_mask(image: Image.Image, predicate, region: tuple[int, int, int, int]) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    pixels = image.load()
    target = mask.load()
    x0, y0, x1, y1 = region
    for y in range(max(0, y0), min(image.height, y1)):
        for x in range(max(0, x0), min(image.width, x1)):
            red, green, blue, alpha = pixels[x, y]
            if alpha >= 16 and predicate(red, green, blue):
                target[x, y] = 255
    return mask


def restricted(mask: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    region = Image.new("L", mask.size, 0)
    ImageDraw.Draw(region).rectangle(box, fill=255)
    return ImageChops.multiply(mask, region)


def shift_mask(mask: Image.Image, dx: int, dy: int = 0) -> Image.Image:
    shifted = Image.new("L", mask.size, 0)
    source_box = (max(0, -dx), max(0, -dy), min(mask.width, mask.width - dx), min(mask.height, mask.height - dy))
    target = (max(0, dx), max(0, dy))
    if source_box[2] > source_box[0] and source_box[3] > source_box[1]:
        shifted.paste(mask.crop(source_box), target)
    return shifted


def shift_image(image: Image.Image, dx: int, dy: int = 0) -> Image.Image:
    shifted = Image.new("RGBA", image.size, (0, 0, 0, 0))
    source_box = (max(0, -dx), max(0, -dy), min(image.width, image.width - dx), min(image.height, image.height - dy))
    target = (max(0, dx), max(0, dy))
    if source_box[2] > source_box[0] and source_box[3] > source_box[1]:
        shifted.alpha_composite(image.crop(source_box), target)
    return shifted


def reposition_pair(image: Image.Image, left_dx: int, right_dx: int) -> Image.Image:
    """Move the two ear halves independently while retaining their pixels."""
    midpoint = image.width // 2
    left_region = Image.new("L", image.size, 0)
    right_region = Image.new("L", image.size, 0)
    ImageDraw.Draw(left_region).rectangle((0, 0, midpoint - 1, image.height), fill=255)
    ImageDraw.Draw(right_region).rectangle((midpoint, 0, image.width - 1, image.height), fill=255)
    left = Image.new("RGBA", image.size, (0, 0, 0, 0))
    right = Image.new("RGBA", image.size, (0, 0, 0, 0))
    left.paste(image, (0, 0), left_region)
    right.paste(image, (0, 0), right_region)
    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    result.alpha_composite(shift_image(left, left_dx))
    result.alpha_composite(shift_image(right, right_dx))
    return result


def mirror_left_from_right(image: Image.Image) -> Image.Image:
    """Use the right half as the canonical rear-ear shape for the left half."""
    midpoint = image.width // 2
    right = image.crop((midpoint, 0, image.width, image.height))
    left = right.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    result.alpha_composite(left, (0, 0))
    result.alpha_composite(right, (midpoint, 0))
    return result


def restrict_image(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rectangle(box, fill=255)
    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    result.paste(image, (0, 0), ImageChops.multiply(image.getchannel("A"), mask))
    return result


def simplify_eye_highlights(image: Image.Image) -> Image.Image:
    """Flatten small white iris highlights into the local blue iris color.

    The base prototype uses deliberately simple eyes.  Large white regions
    are retained as sclera; only small disconnected bright islands are
    recolored, so the eye keeps its readable shape without a costly glossy
    highlight treatment.
    """
    pixels = image.load()
    bright = {
        (x, y)
        for y in range(image.height)
        for x in range(image.width)
        if pixels[x, y][3] >= 180 and min(pixels[x, y][:3]) >= 220
    }
    components: list[list[tuple[int, int]]] = []
    while bright:
        start = bright.pop()
        queue = [start]
        component = [start]
        while queue:
            x, y = queue.pop()
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if neighbor in bright:
                    bright.remove(neighbor)
                    queue.append(neighbor)
                    component.append(neighbor)
        if len(component) < 80:
            components.append(component)

    for component in components:
        samples: list[tuple[int, int, int]] = []
        for x, y in component:
            for nx in range(max(0, x - 3), min(image.width, x + 4)):
                for ny in range(max(0, y - 3), min(image.height, y + 4)):
                    red, green, blue, alpha = pixels[nx, ny]
                    if alpha >= 180 and blue >= red + 20 and blue >= green + 10:
                        samples.append((red, green, blue))
        if samples:
            color = tuple(round(sum(channel) / len(samples)) for channel in zip(*samples))
        else:
            color = (48, 103, 196)
        for x, y in component:
            red, green, blue, alpha = pixels[x, y]
            pixels[x, y] = (*color, alpha)
    return image


def make_back_ear_silhouette(source: Image.Image, skin: tuple[int, int, int, int]) -> Image.Image:
    """Create flat rear ear lobes with a fuller top and tapered lower tip.

    The rear view must not reuse the front ear's concha.  A vertically
    asymmetric silhouette also prevents the ear from reading upside down:
    the upper attachment is fuller and the lower portion tapers away.
    """
    alpha = source.getchannel("A")
    result = Image.new("RGBA", source.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(result)
    for region in ((0, 0, source.width // 2, source.height), (source.width // 2, 0, source.width, source.height)):
        local = alpha.crop(region).getbbox()
        if local is None:
            continue
        x0, y0, x1, y1 = local
        x0 += region[0]
        x1 += region[0]
        # Reduce the front-ear shape to a small outer lobe and remove all
        # inner helix/concha details that should not be visible from behind.
        width = max(16, round((x1 - x0) * 0.68))
        height = max(28, round((y1 - y0) * 0.78))
        center_x = (x0 + x1) // 2
        center_y = (y0 + y1) // 2
        box = (
            center_x - width // 2,
            center_y - height // 2,
            center_x + width // 2,
            center_y + height // 2,
        )
        # A rear view should read as a flat outer lobe, not as a front-facing
        # ear with a visible concha or canal.  Keep the top narrow and let the
        # upper half carries the width and the lower half tapers smaller, which
        # matches the intended simplified rear-ear silhouette.
        bx0, by0, bx1, by1 = box
        width_px = bx1 - bx0
        height_px = by1 - by0
        cx = (bx0 + bx1) // 2
        draw.polygon(
            (
                (cx - round(width_px * 0.42), by0),
                (cx + round(width_px * 0.42), by0),
                (bx1, by0 + round(height_px * 0.24)),
                (cx + round(width_px * 0.12), by0 + round(height_px * 0.64)),
                (cx + round(width_px * 0.06), by1),
                (cx - round(width_px * 0.06), by1),
                (cx - round(width_px * 0.12), by0 + round(height_px * 0.64)),
                (bx0, by0 + round(height_px * 0.24)),
            ),
            fill=skin,
        )
    return result


def transformed_layer(source: Image.Image, mask: Image.Image, bbox: tuple[int, int, int, int]) -> Image.Image:
    crop = source.crop(bbox).convert("RGBA")
    crop.putalpha(ImageChops.multiply(mask, foreground_mask(source)).crop(bbox))
    scale = TARGET_HEIGHT / (bbox[3] - bbox[1])
    width = max(1, round((bbox[2] - bbox[0]) * scale))
    crop = crop.resize((width, TARGET_HEIGHT), Image.Resampling.LANCZOS)
    pixels = crop.load()
    for y in range(crop.height):
        for x in range(crop.width):
            red, green, blue, opacity = pixels[x, y]
            # LANCZOS creates a few almost-transparent colored pixels outside
            # the contour. On the dark preview/GIF background they read as a
            # noisy halo, so discard the fringe while retaining the solid
            # outline and skin edge.
            if opacity < 32 or (opacity and is_magenta(red, green, blue)):
                pixels[x, y] = (red, green, blue, 0)
    canvas = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    canvas.alpha_composite(crop, ((CELL_SIZE - width) // 2, BASELINE_Y - TARGET_HEIGHT))
    return canvas


def split_cell(base: Image.Image, features: Image.Image, direction: str) -> dict[str, Image.Image]:
    base_mask = foreground_mask(base)
    base_bbox = base_mask.getbbox()
    feature_mask = foreground_mask(features)
    feature_bbox = feature_mask.getbbox()
    if base_bbox is None or feature_bbox is None:
        raise ValueError(f"empty rebuild atlas cell: {direction}")

    feature_left, feature_top, feature_right, feature_bottom = feature_bbox
    frame_bbox = (
        min(base_bbox[0], feature_bbox[0]),
        min(base_bbox[1], feature_bbox[1]),
        max(base_bbox[2], feature_bbox[2]),
        max(base_bbox[3], feature_bbox[3]),
    )
    feature_region = feature_bbox
    ears = color_mask(
        features,
        lambda r, g, b: r > 150 and g > 100 and b > 80 and r > g + 5 and g > b + 5,
        feature_region,
    )
    if direction == "right":
        # The source right cell contains the ear on the profile's front side.
        # Keep only that half; the runtime 2/4 exchange will place it on the
        # rear side of the output left profile.
        ears = restricted(ears, ((feature_left + feature_right) // 2, 0, features.width, features.height))
    elif direction == "left":
        # The first source left cell is incomplete and is replaced by the
        # mirrored right-ear anchor below, so this branch is mainly a guard
        # against stray warm pixels in the source cell.
        ears = restricted(ears, (0, 0, (feature_left + feature_right) // 2, features.height))
    if direction == "front":
        midpoint = (feature_left + feature_right) // 2
        left_ear = restricted(ears, (0, 0, midpoint, features.height))
        right_ear = restricted(ears, (midpoint, 0, features.width, features.height))
        ears = ImageChops.lighter(shift_mask(left_ear, 25), shift_mask(right_ear, -25))

    dark = color_mask(
        features,
        lambda r, g, b: r < 115 and g < 115 and b < 145,
        feature_region,
    )
    eyebrow = Image.new("L", features.size, 0)
    if direction != "back":
        brow_bottom = feature_top + round((feature_bottom - feature_top) * 0.38)
        eyebrow = restricted(dark, (feature_left, feature_top, feature_right, brow_bottom))

    if direction == "back":
        eyes = Image.new("L", features.size, 0)
        eyebrow = Image.new("L", features.size, 0)
    else:
        eyes = ImageChops.multiply(feature_mask, ImageChops.invert(ears))
        eyes = ImageChops.multiply(eyes, ImageChops.invert(eyebrow))

    # Do not mirror horizontal directions here. The source atlas already
    # contains a right and a left profile. Mirroring at this stage was the
    # source of the recurring 2/4 reversal; the runtime builder now declares
    # the side-feature source mapping explicitly instead.
    eyes_layer = simplify_eye_highlights(transformed_layer(features, eyes, frame_bbox))
    if direction == "front":
        # The generated front cell leaves small ear-colored edge fragments in
        # the generic foreground mask. Keep the two eyes in the face zone.
        eyes_layer = restrict_image(eyes_layer, (40, 105, 220, 205))
    elif direction == "right":
        # Source right has warm edge fragments around the eye. This clean
        # window is important because source right is assigned to output left.
        eyes_layer = restrict_image(eyes_layer, (90, 75, 195, 215))

    ears_layer = transformed_layer(features, ears, frame_bbox)
    if direction == "front":
        # Remove dark eyebrow/eye fragments that leaked into the warm-color
        # ear mask. Only the two outer ear zones are valid for front ears.
        left_ear = restrict_image(ears_layer, (0, 95, 60, 215))
        right_ear = restrict_image(ears_layer, (196, 95, 255, 215))
        ears_layer = Image.new("RGBA", ears_layer.size, (0, 0, 0, 0))
        ears_layer.alpha_composite(left_ear)
        ears_layer.alpha_composite(right_ear)
    elif direction == "right":
        # Keep only the front source ear. The runtime swaps this source to the
        # output left profile, where it belongs on the rear edge.
        ears_layer = restrict_image(ears_layer, (175, 95, 255, 215))
    elif direction == "back":
        ears_layer = make_back_ear_silhouette(ears_layer, (253, 240, 216, 255))
        # The rear source is ordered opposite to the runtime's left/right
        # convention.  Reflect around the vertical centre line before the
        # pair is repositioned and registered.
        ears_layer = ears_layer.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        # Keep the visually correct right ear as the canonical shape.  The
        # opposite ear is a true centre-line mirror, preventing its lower
        # contour from drifting away from the head silhouette.
        ears_layer = mirror_left_from_right(ears_layer)

    return {
        "face_base": transformed_layer(base, base_mask, frame_bbox),
        # All layers use one union frame. It includes edge ears even when the
        # feature atlas extends beyond the neutral face silhouette.
        "eyes": eyes_layer,
        "eyebrows": transformed_layer(features, eyebrow, frame_bbox),
        "ears": reposition_pair(
            ears_layer,
            12 if direction == "front" else -16 if direction == "back" else 0,
            -16 if direction == "front" else 6 if direction == "back" else 0,
        ),
    }


def main() -> int:
    if not BASE_SOURCE.exists() or not FEATURE_SOURCE.exists():
        raise FileNotFoundError("rebuild atlas inputs are missing")
    base_image = Image.open(BASE_SOURCE).convert("RGBA")
    feature_image = Image.open(FEATURE_SOURCE).convert("RGBA")
    if base_image.size != feature_image.size:
        raise ValueError(f"rebuild atlas input size mismatch: {base_image.size} != {feature_image.size}")

    layers = ("face_base", "eyes", "eyebrows", "ears")
    for layer in layers:
        (OUTPUT / layer).mkdir(parents=True, exist_ok=True)

    manifest = {
        "generator": "process_rebuild_atlas.py",
        "generator_version": 1,
        "base_source": BASE_SOURCE.relative_to(ROOT).as_posix(),
        "feature_source": FEATURE_SOURCE.relative_to(ROOT).as_posix(),
        "directions": list(DIRECTIONS),
        "cell_layout": "2x2_front_right_back_left",
        "canvas": [CELL_SIZE, CELL_SIZE],
        "baseline_y": BASELINE_Y,
        "layers": list(layers),
        "reconstruction_status": "independent_base_and_feature_atlas",
        "randomization_ready": False,
        "directional_feature_policy": {
            "front": {"eyes": 2, "eyebrows": 2, "ears": 2},
            "right": {"eyes": 1, "eyebrows": 1, "ears": 1},
            "back": {"eyes": 0, "eyebrows": 0, "ears": 2},
            "left": {"eyes": 1, "eyebrows": 1, "ears": 1},
        },
        "horizontal_feature_source_map": {
            "right": "left",
            "left": "right",
        },
        "notes": "The face base and facial features are generated independently. Horizontal feature sources are intentionally exchanged at runtime (output right uses source left and output left uses source right) to correct the source atlas 2/4 order; no implicit horizontal mirror is applied. The first atlas omitted the left ear, so the left ear currently mirrors the right ear as a temporary anchor placeholder. Hair remains a separate reconstruction layer.",
        "frames": {},
    }

    generated: dict[str, dict[str, Image.Image]] = {}
    for index, direction in enumerate(DIRECTIONS):
        row, column = divmod(index, 2)
        x0 = round(column * base_image.width / 2)
        x1 = round((column + 1) * base_image.width / 2)
        y0 = round(row * base_image.height / 2)
        y1 = round((row + 1) * base_image.height / 2)
        result = split_cell(base_image.crop((x0, y0, x1, y1)), feature_image.crop((x0, y0, x1, y1)), direction)
        if direction == "left" and "right" in generated:
            # The first feature atlas omitted the left ear. Use a mirrored
            # anchor-compatible placeholder until that ear is redrawn.
            result["ears"] = generated["right"]["ears"].transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        generated[direction] = result
        manifest["frames"][direction] = {}
        for layer, image in result.items():
            path = OUTPUT / layer / f"{direction}.png"
            image.save(path)
            manifest["frames"][direction][layer] = path.relative_to(ROOT).as_posix()

    (OUTPUT / "rebuild_atlas_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("REBUILD_ATLAS_PROCESS_PASS directions=4 layers=4 status=independent_base_and_feature_atlas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
