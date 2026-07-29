from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "prototype" / "assets" / "characters"
CELL_WIDTH = 384
CELL_HEIGHT = 256
GRID_COLUMNS = 4
GRID_ROWS = 4
FRAME_ANCHOR_X = CELL_WIDTH // 2
FRAME_BASELINE_Y = CELL_HEIGHT - 11


def build_foreground_mask(cell: Image.Image) -> Image.Image:
    """Keep the warm ivory mannequin and discard the gray guide background."""
    rgb = cell.convert("RGB")
    warm_mask = Image.new("L", rgb.size, 0)
    source = rgb.load()
    warm_target = warm_mask.load()

    for y in range(rgb.height):
        for x in range(rgb.width):
            red, green, blue = source[x, y]
            warmness = red - blue
            brightness = (red + green + blue) / 3.0
            # The mannequin is warm ivory; the backdrop and guide lines are neutral gray.
            if warmness >= 5 and brightness >= 105:
                warm_target[x, y] = 255

    # Recover only the nearby dark outline. Do not copy light background pixels into alpha.
    expanded = warm_mask.filter(ImageFilter.MaxFilter(5))
    expanded_pixels = expanded.load()
    output = Image.new("L", rgb.size, 0)
    output_pixels = output.load()
    for y in range(rgb.height):
        for x in range(rgb.width):
            red, green, blue = source[x, y]
            brightness = (red + green + blue) / 3.0
            if warm_target[x, y] or (expanded_pixels[x, y] and brightness < 150):
                output_pixels[x, y] = 255

    output = output.filter(ImageFilter.MinFilter(3))
    output = output.filter(ImageFilter.MaxFilter(3))
    return output


def keep_largest_component(mask: Image.Image) -> Image.Image:
    """Discard detached pixels such as the next row bleeding into this cell."""
    width, height = mask.size
    source = mask.load()
    visited = bytearray(width * height)
    largest: list[int] = []

    for y in range(height):
        for x in range(width):
            start = y * width + x
            if visited[start] or source[x, y] == 0:
                continue

            component = [start]
            visited[start] = 1
            for index in component:
                cx = index % width
                cy = index // width
                for nx, ny in (
                    (cx - 1, cy),
                    (cx + 1, cy),
                    (cx, cy - 1),
                    (cx, cy + 1),
                ):
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    neighbor = ny * width + nx
                    if not visited[neighbor] and source[nx, ny] != 0:
                        visited[neighbor] = 1
                        component.append(neighbor)

            if len(component) > len(largest):
                largest = component

    output = bytearray(width * height)
    for index in largest:
        output[index] = 255
    return Image.frombytes("L", (width, height), bytes(output))


def align_frame(rgba: Image.Image, alpha: Image.Image) -> tuple[Image.Image, Image.Image]:
    """Give every frame a stable horizontal center and foot baseline."""
    bbox = alpha.getbbox()
    if bbox is None:
        return rgba, alpha

    current_center_x = (bbox[0] + bbox[2]) / 2.0
    dx = round(FRAME_ANCHOR_X - current_center_x)
    dy = FRAME_BASELINE_Y - bbox[3]

    aligned_rgba = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    aligned_alpha = Image.new("L", alpha.size, 0)
    aligned_rgba.alpha_composite(rgba, (dx, dy))
    aligned_alpha.paste(alpha, (dx, dy))
    return aligned_rgba, aligned_alpha


def bleed_edge_colors(rgba: Image.Image, alpha: Image.Image, passes: int = 5) -> Image.Image:
    """Extrude edge RGB into transparent pixels to prevent filtered halos."""
    output = rgba.copy()
    pixels = output.load()
    alpha_pixels = alpha.load()
    width, height = output.size
    directions = (
        (-1, -1), (0, -1), (1, -1),
        (-1, 0), (1, 0),
        (-1, 1), (0, 1), (1, 1),
    )
    for _ in range(passes):
        updates: list[tuple[int, int, tuple[int, int, int, int]]] = []
        for y in range(height):
            for x in range(width):
                if alpha_pixels[x, y] != 0:
                    continue
                for dx, dy in directions:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height and alpha_pixels[nx, ny] != 0:
                        red, green, blue, _ = pixels[nx, ny]
                        updates.append((x, y, (red, green, blue, 0)))
                        break
        for x, y, color in updates:
            pixels[x, y] = color
    return output


def process_variant(source_name: str, variant_name: str) -> dict[str, object]:
    source_path = ROOT / source_name
    output_dir = OUTPUT_ROOT / variant_name
    frame_dir = output_dir / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)

    source = Image.open(source_path).convert("RGB")
    expected_size = (CELL_WIDTH * GRID_COLUMNS, CELL_HEIGHT * GRID_ROWS)
    if source.size != expected_size:
        raise ValueError(f"{source_path.name} is {source.size}, expected {expected_size}")

    atlas = Image.new("RGBA", source.size, (0, 0, 0, 0))
    idle_atlas = Image.new("RGBA", source.size, (0, 0, 0, 0))
    frame_names: list[list[str]] = []

    for row in range(GRID_ROWS):
        row_names: list[str] = []
        first_frame: Image.Image | None = None
        for column in range(GRID_COLUMNS):
            box = (
                column * CELL_WIDTH,
                row * CELL_HEIGHT,
                (column + 1) * CELL_WIDTH,
                (row + 1) * CELL_HEIGHT,
            )
            cell = source.crop(box)
            alpha = keep_largest_component(build_foreground_mask(cell))
            rgba = cell.convert("RGBA")
            rgba.putalpha(alpha)
            rgba, alpha = align_frame(rgba, alpha)
            rgba = bleed_edge_colors(rgba, alpha)
            if first_frame is None:
                first_frame = rgba.copy()

            atlas.alpha_composite(rgba, (column * CELL_WIDTH, row * CELL_HEIGHT))
            frame_name = f"walk_row{row}_frame{column}.png"
            rgba.save(frame_dir / frame_name)
            row_names.append(frame_name)

        assert first_frame is not None
        for column in range(GRID_COLUMNS):
            idle_atlas.alpha_composite(
                first_frame, (column * CELL_WIDTH, row * CELL_HEIGHT)
            )
        frame_names.append(row_names)

    atlas_path = output_dir / "body_walk_4way.png"
    idle_path = output_dir / "body_idle_4way.png"
    atlas.save(atlas_path)
    idle_atlas.save(idle_path)

    manifest = {
        "variant": variant_name,
        "source": source_name,
        "atlas": atlas_path.relative_to(ROOT).as_posix(),
        "idle_atlas": idle_path.relative_to(ROOT).as_posix(),
        "frame_directory": frame_dir.relative_to(ROOT).as_posix(),
        "cell_size": [CELL_WIDTH, CELL_HEIGHT],
        "columns": GRID_COLUMNS,
        "rows": GRID_ROWS,
        "row_directions": ["front", "right", "back", "left"],
        "frame_order": ["left_contact", "passing", "right_contact", "passing"],
        "frames": frame_names,
        "transparent_background": True,
    }
    manifest_path = output_dir / "animation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    manifests = [
        process_variant(
            "walk-base-4way-male-4frame-sheet.png",
            "male",
        ),
        process_variant(
            "walk-base-4way-female-4frame-sheet.png",
            "female",
        ),
    ]
    print(json.dumps(manifests, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
