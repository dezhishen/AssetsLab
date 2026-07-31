# AssetsLab Local Preview

Open `index.html` from this folder to inspect the current reconstructed head assets.

The page uses project-tracked assets and does not depend on `prototype/test_output/`. Rebuild the runtime assets, refresh the page, and the same preview location remains valid.

The direction table is intentionally explicit: Godot row 1 is the right-facing base and row 3 is the left-facing base; detachable side facial features exchange source 2 and source 4 without an additional horizontal mirror.

Use `body_calibrate.html` to align the complete head group against the four-direction body. The page uses a horizontal neck guide and stores offsets in the ignored `prototype/preview/calibration/body_latest.json` file.

Use `limb_puzzle.html` when the four limbs need to be positioned independently. It exports `limb_puzzle_v1`, preserving the rectangle placement, angle, and layer order for each limb.

The tracked body-pose source of truth is instead
`prototype/assets/characters/limb_puzzle.json` (`limb_puzzle_v1`). Its four
rectangles per frame record position, angle, and `z_order`; retain the explicit
rear/torso/front relationship when drawing final pixels. The page exports the
same schema so the adjusted file can be copied back into that tracked path.
Use `limb_calibrate.html` only if the right-facing candidate later shows a
component offset. It can align the torso, arms, lower body, and feet across all
eight frames and stores offsets in the ignored
`prototype/preview/calibration/body_components_latest.json` file.

Use `body_outline_split.html` to mark the four limb guide lines directly on the
generated outline. It exports `body_outline_split_v1`; the server stores the
optional local result in the ignored `body_outline_split_latest.json` file.

The RGS open-source character is a motion reference, not final character art.
Run `tools/capture_walk_gif.ps1 -RgsWalkReference` to render its complete
eight-frame loop without opening the Godot editor. The project will later redraw
the QQTang-style body against the same pose timing.
