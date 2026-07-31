from __future__ import annotations

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "prototype/assets/characters/limb_puzzle.json"
OUTPUT = ROOT / "prototype/assets/characters/generated/skeleton_workflows"


def load_source() -> dict:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    if payload.get("schema") != "limb_puzzle_v1" or len(payload.get("frames", [])) != 8:
        raise ValueError("expected an 8-frame limb_puzzle_v1 source")
    return payload


def make_workflow(source: dict, workflow: str) -> dict:
    result = copy.deepcopy(source)
    result["schema"] = "skeleton_walk_workflow_v1"
    result["source_schema"] = source["schema"]
    result["workflow"] = workflow
    result["art_source"] = "prototype/assets/characters/generated/body_outline_split_v2_manual_from_project"
    result["rig_target"] = "Godot 4.6.2 Skeleton2D rigid cutout prototype"
    if workflow == "A_both_legs_pass":
        result["description"] = "Baseline: both feet use the authored passing pose in frames 2 and 6."
        result["passing_policy"] = "both_legs_move_to_passing_pose"
        return result

    if workflow != "B_front_leg_only_pass":
        raise ValueError(workflow)

    result["description"] = (
        "Experiment: in each passing pose only the leading/front leg retracts; "
        "the trailing/rear leg keeps the previous support position."
    )
    result["passing_policy"] = "leading_leg_only_retracts"
    result["leading_leg_by_phase"] = {"frames_2_3": "right_foot", "frames_6_7": "left_foot"}
    # Frame indices 2 and 6 are the 1-based third and seventh frames. Keep the
    # rear foot from the preceding down pose while retaining the authored target
    # pose for the leading foot. Arms and torso remain identical to workflow A.
    for passing_index, rear_index, rear_name in ((2, 1, "left_foot"), (6, 5, "right_foot")):
        result["frames"][passing_index]["parts"][rear_name] = copy.deepcopy(
            source["frames"][rear_index]["parts"][rear_name]
        )
    return result


def main() -> int:
    source = load_source()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    outputs = []
    for workflow in ("A_both_legs_pass", "B_front_leg_only_pass"):
        payload = make_workflow(source, workflow)
        path = OUTPUT / f"{workflow}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        outputs.append(path.relative_to(ROOT).as_posix())
    print("SKELETON_WORKFLOW_VARIANTS_PASS " + " ".join(outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
