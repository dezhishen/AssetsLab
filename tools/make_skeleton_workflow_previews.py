from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ("A_both_legs_pass", "B_front_leg_only_pass")
BACKGROUND = (22, 25, 39)


def frame_paths(workflow: str) -> list[Path]:
    directory = ROOT / "prototype/test_output/skeleton_workflows" / workflow
    paths = [directory / f"frame_{index:04d}.png" for index in range(8)]
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing capture frames for {workflow}: {missing[0]}")
    return paths


def crop_frames(paths: list[Path]) -> list[Image.Image]:
    images = [Image.open(path).convert("RGBA") for path in paths]
    union = None
    for image in images:
        rgb = image.convert("RGB")
        mask = Image.new("L", rgb.size, 0)
        pixels = rgb.load()
        mask_pixels = mask.load()
        for y in range(rgb.height):
            for x in range(rgb.width):
                if pixels[x, y] != BACKGROUND:
                    mask_pixels[x, y] = 255
        bbox = mask.getbbox()
        if bbox is not None:
            union = bbox if union is None else (
                min(union[0], bbox[0]),
                min(union[1], bbox[1]),
                max(union[2], bbox[2]),
                max(union[3], bbox[3]),
            )
    if union is None:
        raise ValueError("capture frames contain no character pixels")
    pad = 24
    left = max(0, union[0] - pad)
    top = max(0, union[1] - pad)
    right = min(images[0].width, union[2] + pad)
    bottom = min(images[0].height, union[3] + pad)
    return [image.crop((left, top, right, bottom)) for image in images]


def save_gif(frames: list[Image.Image], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
        disposal=2,
    )


def save_contact(frames_by_workflow: dict[str, list[Image.Image]], output: Path) -> None:
    cell_width = max(frame.width for frames in frames_by_workflow.values() for frame in frames)
    cell_height = max(frame.height for frames in frames_by_workflow.values() for frame in frames)
    label_height = 28
    row_height = cell_height + label_height
    sheet = Image.new("RGB", (cell_width * 8, row_height * 2), BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    for row, workflow in enumerate(WORKFLOWS):
        for index, frame in enumerate(frames_by_workflow[workflow]):
            x = index * cell_width
            y = row * row_height + label_height
            sheet.paste(frame.convert("RGB"), (x, y))
            draw.text((x + 4, row * row_height + 7), f"{workflow[0]}{index + 1}", fill=(235, 235, 235))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build GIF/contact previews for Skeleton2D A/B workflows")
    parser.add_argument("--output-dir", default="prototype/preview/assets")
    args = parser.parse_args()
    output_dir = ROOT / args.output_dir
    frames_by_workflow = {}
    for workflow in WORKFLOWS:
        frames = crop_frames(frame_paths(workflow))
        frames_by_workflow[workflow] = frames
        save_gif(frames, output_dir / f"skeleton_workflow_{workflow}.gif")
    save_contact(frames_by_workflow, output_dir / "skeleton_workflow_A_B_contact.png")
    print("SKELETON_WORKFLOW_PREVIEWS_PASS " + " ".join(WORKFLOWS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
