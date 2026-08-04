#!/usr/bin/env python3
"""Cross-platform AssetsLab command line interface.

A single pure-Python entry point that mirrors the Windows PowerShell tooling,
so the same workflow runs on Windows, Linux and macOS:

    python tools/assetslab.py doctor
    python tools/assetslab.py test [options]
    python tools/assetslab.py capture-walk [options]
    python tools/assetslab.py stage <view> <stage> [--godot PATH]
    python tools/assetslab.py preview [--port N] [--directory DIR]
    python tools/assetslab.py publish [--name TAG]
    python tools/assetslab.py run-script <script.py> [args...]

Mapping to the legacy PowerShell scripts:
    test         -> tools/run_headless_tests.ps1
    capture-walk -> tools/capture_walk_gif.ps1
    stage        -> tools/capture_*_stage.ps1
    preview      -> tools/lan_preview_server.py (+ serve_preview.ps1)
    publish      -> tools/publish_preview.py
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from godot_runner import (  # noqa: E402
    IS_WINDOWS,
    PREVIEW_ASSETS,
    PREVIEW_ROOT,
    PROTOTYPE_ROOT,
    ROOT,
    SKELETON_PIPELINE,
    TEST_OUTPUT,
    ResolutionError,
    godot_base_args,
    python_env,
    resolve_godot,
    resolve_python,
    run,
)

TOOLS = ROOT / "tools"

# view -> stage -> (godot test script, frame directory name, expected output)
STAGES: dict[str, dict[str, tuple[str, str | None, str]]] = {
    "front": {
        "skeleton": ("front_skeleton_stage_test.gd", None, "front_base.png"),
        "legs": ("front_leg_cycle_stage_test.gd", "front_legs", "front_legs.gif"),
        "pelvis": ("front_pelvis_bob_stage_test.gd", "front_pelvis_bob", "front_pelvis_bob.gif"),
        "arms": ("front_arm_swing_stage_test.gd", "front_arm_swing", "front_arm_swing.gif"),
    },
    "side": {
        "skeleton": ("side_skeleton_stage_test.gd", None, "side_base.png"),
        "legs": ("side_leg_cycle_stage_test.gd", "side_legs", "side_legs.gif"),
        "pelvis": ("side_pelvis_bob_stage_test.gd", "side_pelvis_bob", "side_pelvis_bob.gif"),
        "arms": ("side_arm_swing_stage_test.gd", "side_arm_swing", "side_arm_swing.gif"),
    },
    "back": {
        "skeleton": ("back_skeleton_stage_test.gd", None, "back_base.png"),
        "legs": ("back_leg_cycle_stage_test.gd", "back_legs", "back_legs.gif"),
    },
}


# ------------------------------------------------------------------ helpers --


def _parse_seed(output: str) -> int | None:
    for line in output.splitlines():
        if line.startswith("RANDOM_APPEARANCE_SEED="):
            return int(line.split("=", 1)[1])
    return None


def _run_python_tool(python: str, script_name: str, extra: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    return run([python, str(TOOLS / script_name), *extra], env=env, check=False)


def _generate_appearance(python: str, args: argparse.Namespace, *, output: Path, both: bool, female_flag: bool) -> int:
    extra = ["--output", str(output)]
    if both:
        extra += ["--both"]
    elif female_flag:
        extra += ["--female"]
    if getattr(args, "compact", False):
        extra += ["--compact"]
    if args.appearance_seed is not None:
        extra += ["--seed", str(args.appearance_seed)]
    process = _run_python_tool(python, "generate_random_appearance.py", extra)
    print(process.stdout, end="")
    if process.stderr:
        print(process.stderr, end="")
    if process.returncode != 0:
        raise SystemExit("Random appearance generation failed.")
    seed = _parse_seed(process.stdout)
    if seed is None:
        raise SystemExit("Random appearance generator did not return a seed.")
    return seed


def _validate_appearance(python: str, root: Path, both: bool) -> None:
    extra = ["--root", str(root)]
    if both:
        extra += ["--both"]
    process = _run_python_tool(python, "validate_random_appearance.py", extra)
    print(process.stdout, end="")
    if process.stderr:
        print(process.stderr, end="")
    if process.returncode != 0:
        raise SystemExit("Random appearance validation failed.")


def _validate_asset_stack(python: str, args: argparse.Namespace) -> None:
    """Run the static asset validators used by the headless test pipeline."""
    env = python_env()
    env["CHIBI_ASSET_ROOT"] = "chibi_compact" if args.compact else "chibi"
    if getattr(args, "rebuild_head", False):
        _run_or_die(python, "validate_rebuild_runtime_anchors.py", [], env=env)
    _run_or_die(python, "validate_chibi_frames.py", [], env=env)
    _run_or_die(python, "validate_limb_occlusion.py", [], env=env)
    _run_or_die(python, "validate_face_variants.py", [], env=env)
    if getattr(args, "base_features", False):
        _run_or_die(python, "validate_base_features.py", [], env=env)


def _run_or_die(python: str, script_name: str, extra: list[str], env: dict | None = None) -> None:
    process = _run_python_tool(python, script_name, extra, env=env)
    if process.stdout:
        print(process.stdout, end="")
    if process.stderr:
        print(process.stderr, end="")
    if process.returncode != 0:
        raise SystemExit(f"{script_name} failed (exit {process.returncode}).")


def _smoke_user_args(args: argparse.Namespace, seed: int, female: bool) -> list[str]:
    user = []
    if female:
        user.append("--female")
    if args.compact:
        user.append("--compact")
    if args.base_features:
        user.append("--base-features")
    else:
        user.append(f"--appearance-seed={seed}")
    if args.rebuild_head:
        user.append("--rebuild-head")
    if getattr(args, "rebuild_body", False):
        user.append("--rebuild-body")
    if args.rgs_body_right:
        user.append("--rgs-body-right")
    if args.rgs_walk_reference:
        user.append("--rgs-walk-reference")
    if args.bombo_body_right:
        user.append("--bombo-body-right")
    if args.milestone_body_right:
        user.append("--milestone-body-right")
    if args.vertical_candidate:
        user.append("--vertical-body-candidate")
    return user


def _walk_user_args(args: argparse.Namespace, seed: int) -> list[str]:
    user = []
    if args.female:
        user.append("--female")
    if args.compact:
        user.append("--compact")
    if args.base_features:
        user.append("--base-features")
    else:
        user.append(f"--appearance-seed={seed}")
    if args.rebuild_head:
        user.append("--rebuild-head")
    if args.latest_generated_body:
        user.append("--latest-generated-body")
    if args.vertical_candidate:
        user.append("--vertical-body-candidate")
    if args.vertical_only:
        user.append("--vertical-only")
    if args.rgs_walk_reference:
        user.append("--rgs-walk-reference")
    if args.rgs_body_right:
        user.append("--rgs-body-right")
    if args.bombo_body_right:
        user.append("--bombo-body-right")
    if args.milestone_body_right:
        user.append("--milestone-body-right")
    if args.right_only:
        user.append("--right-only")
    return user


def _gif_name(args: argparse.Namespace) -> str:
    if args.bombo_body_right:
        return "movement_bombo_body_candidate.gif"
    if args.rgs_body_right:
        return "movement_rgs_body_candidate.gif"
    if args.rgs_walk_reference:
        return "movement_rgs_reference.gif"
    if args.latest_generated_body:
        return "movement_latest_generated_body.gif"
    if args.vertical_candidate:
        return "movement_vertical_body_candidate.gif"
    if args.rebuild_head and args.right_only:
        return "movement_rebuild_head_right_only.gif"
    if args.rebuild_head:
        return "movement_rebuild_head.gif"
    if args.milestone_body_right:
        return "movement_milestone_body_right_only.gif" if args.right_only else "movement_milestone_body.gif"
    if args.base_features:
        return "movement_walk_base_features_v1.gif"
    if args.compact:
        return "movement_walk_compact.gif"
    return "movement_walk.gif"


# ----------------------------------------------------------------- commands --


def cmd_doctor(args: argparse.Namespace) -> int:
    def try_resolve(label: str, fn):
        try:
            value = fn()
        except ResolutionError as error:
            value = f"NOT FOUND ({error})"
        print(f"{label}: {value}")

    try_resolve("Godot", lambda: resolve_godot(args.godot))
    try_resolve("Python", lambda: resolve_python(args.python))
    print(f"Prototype root: {PROTOTYPE_ROOT}")
    print(f"Test output:   {TEST_OUTPUT}")
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    python = resolve_python(args.python)
    godot = resolve_godot(args.godot)

    random_root = TEST_OUTPUT / "random_appearance"
    if args.female:
        seed = _generate_appearance(python, args, output=random_root, both=True, female_flag=True)
        _validate_appearance(python, random_root, both=True)
    else:
        package_root = random_root / "male"
        seed = _generate_appearance(python, args, output=package_root, both=False, female_flag=False)
        _validate_appearance(python, package_root, both=False)

    _validate_asset_stack(python, args)

    # Godot headless asset import (mirrors run_headless_tests.ps1).
    TEST_OUTPUT.mkdir(parents=True, exist_ok=True)
    import_log = TEST_OUTPUT / "headless_import.log"
    import_cmd = [godot, "--headless", "--editor", "--import", "--path", str(PROTOTYPE_ROOT), "--quit"]
    import_process = run(import_cmd, check=False)
    import_log.write_text((import_process.stdout or "") + (import_process.stderr or ""), encoding="utf-8")
    if import_process.returncode != 0:
        raise SystemExit("Godot headless asset import failed.")

    def smoke(female: bool) -> None:
        prefix = "headless_compact" if args.compact else "headless"
        log_name = f"{prefix}_{'female' if female else 'male'}.log"
        log_path = TEST_OUTPUT / log_name
        user = _smoke_user_args(args, seed, female)
        cmd = [godot, *godot_base_args(script="res://tests/smoke_test.gd", log_file=log_path)]
        if user:
            cmd += ["--", *user]
        print(f"Running headless smoke test ({'female' if female else 'male'})")
        process = run(cmd, check=False)
        if process.stdout:
            print(process.stdout, end="")
        if process.stderr:
            print(process.stderr, end="")
        if process.returncode != 0:
            raise SystemExit(f"Godot headless smoke test failed (exit {process.returncode}).")
        if "SMOKE_TEST_PASS" not in (process.stdout or "") and "SMOKE_TEST_PASS" not in (process.stderr or ""):
            raise SystemExit("Godot headless smoke test did not report SMOKE_TEST_PASS.")

    smoke(female=False)
    if args.female:
        smoke(female=True)

    print("HEADLESS_TESTS_PASS")
    return 0


def cmd_capture_walk(args: argparse.Namespace) -> int:
    python = resolve_python(args.python)
    godot = resolve_godot(args.godot)

    if args.milestone_body_right:
        args.right_only = True
    if args.vertical_only:
        args.vertical_candidate = True

    random_root = TEST_OUTPUT / "random_appearance"
    gender = "female" if args.female else "male"
    package_root = random_root / gender
    seed = _generate_appearance(python, args, output=package_root, both=False, female_flag=args.female)
    _validate_appearance(python, package_root, both=False)
    if args.base_features:
        _run_or_die(python, "validate_base_features.py", [])

    gif_path = TEST_OUTPUT / _gif_name(args)
    log_path = TEST_OUTPUT / "capture.log"
    user = _walk_user_args(args, seed)
    cmd = [godot, *godot_base_args(
        script="res://tests/capture_test.gd",
        log_file=log_path,
        fixed_fps=12,
    )]
    if user:
        cmd += ["--", *user]
    process = run(cmd, check=False)
    if process.stdout:
        print(process.stdout, end="")
    if process.stderr:
        print(process.stderr, end="")
    if process.returncode != 0:
        raise SystemExit(f"Godot capture test failed (exit {process.returncode}).")
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    if "CAPTURE_TEST_PASS" not in log_text:
        raise SystemExit("Godot capture test did not report CAPTURE_TEST_PASS.")

    frame_dir = TEST_OUTPUT / "capture_frames"
    process = _run_python_tool(python, "make_gif.py", ["--input", str(frame_dir), "--output", str(gif_path), "--fps", "12"])
    if process.stdout:
        print(process.stdout, end="")
    if process.stderr:
        print(process.stderr, end="")
    if process.returncode != 0:
        raise SystemExit("GIF conversion failed.")

    # Mirror the preview copy rules from capture_walk_gif.ps1.
    preview_name: str | None = None
    if args.rgs_walk_reference:
        preview_name = "movement_rgs_reference.gif"
    elif args.rgs_body_right:
        preview_name = "movement_rgs_body_candidate.gif"
    elif args.bombo_body_right:
        preview_name = "movement_bombo_body_candidate.gif"
    elif args.milestone_body_right:
        preview_name = "movement_milestone_body_right_only.gif" if args.right_only else "movement_milestone_body.gif"
    elif args.vertical_only:
        preview_name = "movement_vertical_body_candidate.gif"
    elif args.rebuild_head and args.right_only:
        preview_name = "movement_rebuild_head_right_only.gif"
    if preview_name:
        PREVIEW_ASSETS.mkdir(parents=True, exist_ok=True)
        shutil.copy2(gif_path, PREVIEW_ASSETS / preview_name)
        print(f"PREVIEW_COPY={PREVIEW_ASSETS / preview_name}")

    print(f"CAPTURE_COMPLETE={gif_path}")
    return 0


def cmd_stage(args: argparse.Namespace) -> int:
    view_stages = STAGES.get(args.view)
    if view_stages is None or args.stage not in view_stages:
        available = {view: list(stages) for view, stages in STAGES.items()}
        raise SystemExit(f"Unknown stage '{args.view} {args.stage}'. Available stages: {json.dumps(available)}")
    test_script, frame_dir_name, expected_name = view_stages[args.stage]

    godot = resolve_godot(args.godot)
    python = resolve_python(args.python)

    cmd = [godot, *godot_base_args(script=f"res://tests/{test_script}")]
    process = run(cmd, check=False)
    if process.stdout:
        print(process.stdout, end="")
    if process.stderr:
        print(process.stderr, end="")
    if process.returncode != 0:
        raise SystemExit(f"{args.view} {args.stage} stage failed (exit {process.returncode}).")

    SKELETON_PIPELINE.mkdir(parents=True, exist_ok=True)
    if frame_dir_name is not None:
        frame_dir = SKELETON_PIPELINE / frame_dir_name
        frames = sorted(frame_dir.glob("frame_*.png")) if frame_dir.is_dir() else []
        if len(frames) != 8:
            raise SystemExit(f"{args.view} {args.stage} stage did not produce eight frames in {frame_dir}.")
        gif_path = SKELETON_PIPELINE / expected_name
        gif_process = _run_python_tool(python, "make_gif.py", ["--input", str(frame_dir), "--output", str(gif_path), "--fps", "8"])
        if gif_process.stdout:
            print(gif_process.stdout, end="")
        if gif_process.stderr:
            print(gif_process.stderr, end="")
        if gif_process.returncode != 0:
            raise SystemExit("Stage GIF conversion failed.")
        output = gif_path
    else:
        output = SKELETON_PIPELINE / expected_name
        if not output.exists():
            raise SystemExit(f"{args.view} {args.stage} stage did not produce expected output: {output}")

    print(f"{args.view}_{args.stage}_CAPTURE_PASS={output}")
    return 0


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def cmd_preview(args: argparse.Namespace) -> int:
    python = resolve_python(args.python)
    if _port_in_use(args.port):
        print(f"PREVIEW_SERVER_ALREADY_RUNNING port={args.port}")
        return 0
    directory = Path(args.directory).resolve()
    if not directory.is_dir():
        raise SystemExit(f"Preview directory does not exist: {directory}")
    print(f"PREVIEW_SERVER_ROOT={directory}")
    print(f"http://127.0.0.1:{args.port}/")
    cmd = [python, str(TOOLS / "lan_preview_server.py"), "--port", str(args.port), "--directory", str(directory)]
    return subprocess.call(cmd)


def cmd_publish(args: argparse.Namespace) -> int:
    python = resolve_python(args.python)
    extra = ["--name", args.name] if args.name else []
    process = _run_python_tool(python, "publish_preview.py", extra)
    print(process.stdout, end="")
    if process.stderr:
        print(process.stderr, end="")
    if process.returncode != 0:
        raise SystemExit("Preview snapshot publish failed.")
    return 0


def cmd_run_script(args: argparse.Namespace) -> int:
    python = resolve_python(args.python)
    script = Path(args.script)
    script = script if script.is_absolute() else TOOLS / script
    if not script.is_file():
        raise SystemExit(f"Tool script not found: {script}")
    return subprocess.call([python, str(script), *args.script_args])


# -------------------------------------------------------------------- main --


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="assetslab",
        description="Cross-platform AssetsLab CLI (mirrors the Windows PowerShell tooling).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_tool_args(p):
        p.add_argument("--godot", help="Path to a Godot executable (or GODOT_BIN/GODOT_PATH).")
        p.add_argument("--python", help="Path to a Python executable (or PYTHON_BIN).")

    def add_mode_flags(p, *, capture: bool):
        p.add_argument("--female", action="store_true", help="Use the female-presenting base.")
        p.add_argument("--compact", action="store_true", help="Use the compact-stride candidate assets.")
        p.add_argument("--base-features", action="store_true", help="Validate the fixed base feature set instead of a random seed.")
        p.add_argument("--rebuild-head", action="store_true", help="Use the calibrated rebuild head runtime.")
        if capture:
            p.add_argument("--latest-generated-body", action="store_true")
            p.add_argument("--vertical-only", action="store_true")
            p.add_argument("--right-only", action="store_true")
        p.add_argument("--rebuild-body", action="store_true")
        p.add_argument("--vertical-candidate", action="store_true")
        p.add_argument("--rgs-body-right", action="store_true")
        p.add_argument("--bombo-body-right", action="store_true")
        p.add_argument("--rgs-walk-reference", action="store_true")
        p.add_argument("--milestone-body-right", action="store_true")
        p.add_argument("--appearance-seed", type=int, help="Reproducible appearance seed.")
        add_tool_args(p)

    p = sub.add_parser("doctor", help="Print the resolved Godot/Python tool paths.")
    add_tool_args(p)

    p = sub.add_parser("test", help="Run headless smoke tests (run_headless_tests.ps1).")
    add_mode_flags(p, capture=False)

    p = sub.add_parser("capture-walk", help="Capture a four-direction walk GIF (capture_walk_gif.ps1).")
    add_mode_flags(p, capture=True)

    p = sub.add_parser("stage", help="Capture one skeleton pipeline stage (capture_*_stage.ps1).")
    p.add_argument("view", choices=list(STAGES), help="front / side / back")
    p.add_argument("stage", choices=sorted({s for stages in STAGES.values() for s in stages}), help="skeleton / legs / pelvis / arms")
    add_tool_args(p)

    p = sub.add_parser("preview", help="Start the LAN preview server (lan_preview_server.py).")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--directory", default=str(PREVIEW_ROOT), help="Directory to serve (default: prototype/preview).")
    p.add_argument("--python", help="Python executable.")

    p = sub.add_parser("publish", help="Build and publish a preview snapshot (publish_preview.py).")
    p.add_argument("--name", help="Optional English snapshot label.")
    p.add_argument("--python", help="Python executable.")

    p = sub.add_parser("run-script", help="Run any Python tool script (e.g. build_body_vertical_update.py).")
    p.add_argument("script", help="Script name under tools/, or a path.")
    p.add_argument("script_args", nargs=argparse.REMAINDER, help="Extra arguments forwarded to the script.")
    p.add_argument("--python", help="Python executable.")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "doctor": cmd_doctor,
        "test": cmd_test,
        "capture-walk": cmd_capture_walk,
        "stage": cmd_stage,
        "preview": cmd_preview,
        "publish": cmd_publish,
        "run-script": cmd_run_script,
    }
    try:
        return handlers[args.command](args)
    except ResolutionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
