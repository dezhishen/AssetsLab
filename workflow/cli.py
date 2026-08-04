"""Command line interface for the workflow engine (thin wrapper over the SDK).

CLI is the AI-facing scheduling channel: every command maps to one SDK call,
outputs local image absolute paths, and supports ``--json`` for machine
readability.  The Web console uses the same SDK through the HTTP API.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .model import BODY_NAMES, WorkflowDef
from .runner import WorkflowRunner, create_instance, list_instances
from .store import Store

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = ROOT / "run"
DEFAULT_DEFINITION_ROOT = ROOT / "workflow" / "definitions"
DEFAULT_TEMPLATE_ROOT = ROOT / "workflow" / "templates"
DEFAULT_BODY_ROOT = ROOT / "workflow" / "body"


def _emit(data: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(_human(data))


def _human(data: object) -> str:
    if isinstance(data, list):
        if not data:
            return "(no workflow instances)"
        lines = []
        for item in data:
            if isinstance(item, dict) and "workflow_id" in item:
                lines.append(
                    f"{item.get('workflow_id'):<28} {item.get('definition_id'):<12} "
                    f"progress={item.get('progress'):>5} v{item.get('version')} {item.get('updated_at', '')}"
                )
            elif isinstance(item, dict):
                lines.append("  ".join(f"{key}={value}" for key, value in item.items()))
            else:
                lines.append(str(item))
        return "\n".join(lines)
    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            if key == "actions":
                continue
            lines.append(f"{key}: {value}")
        actions = data.get("actions")
        if isinstance(actions, dict):
            lines.append("actions:")
            for aid, st in actions.items():
                if isinstance(st, dict):
                    note = f" note={st.get('note')!r}" if st.get("note") else ""
                    lines.append(f"  {aid:<28} {st.get('status'):<8} approved={st.get('approved')}{note}")
        return "\n".join(lines)
    return str(data)


def _definition(definitions_root: Path, definition_id: str) -> WorkflowDef:
    path = definitions_root / f"{definition_id}.json"
    if not path.exists():
        raise SystemExit(f"definition not found: {definition_id} ({path})")
    return WorkflowDef.load(path)


def _apply_body(body: dict, item: str) -> None:
    """Parse one ``--body NAME=VALUE`` into the body dict, validating the name."""
    if "=" not in item:
        raise SystemExit(f"--body expects NAME=VALUE, got: {item}")
    key, value = item.split("=", 1)
    if key not in BODY_NAMES:
        raise SystemExit(f"unknown body proportion: {key} (known: {', '.join(BODY_NAMES)})")
    body[key] = float(value)


def _store(run_root: Path, workflow_id: str) -> Store:
    return Store(run_root, workflow_id)


def _runner(args: argparse.Namespace, workflow_id: str | None = None) -> WorkflowRunner:
    store = _store(args.run_root, workflow_id or args.workflow)
    if not store.exists():
        raise SystemExit(f"workflow instance not found: {store.workflow_id} (use 'new' first)")
    definition = _definition(args.definition_root, store.load().get("definition_id", "default"))
    # root is the repository root (for tool paths / cwd / dist); the run state
    # lives under args.run_root via the store.
    return WorkflowRunner(ROOT, definition, store.workflow_id, store)


def cmd_list(args: argparse.Namespace) -> int:
    _emit(list_instances(ROOT, args.run_root), args.json)
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    workflow_id = args.id or args.definition
    body: dict[str, float] = {}
    for item in args.body or []:
        _apply_body(body, item)
    try:
        result = create_instance(ROOT, args.run_root, workflow_id, args.definition,
                                 args.template, args.body_template, body or None,
                                 args.definition_root, args.template_root, args.body_root)
    except (KeyError, RuntimeError) as error:
        _emit({"ok": False, "error": str(error)}, args.json)
        return 1
    _emit(result, args.json)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    runner = _runner(args)
    _emit(runner.status_view(), args.json)
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    runner = _runner(args)
    _emit({"next": runner.next()}, args.json)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    runner = _runner(args)
    params: dict[str, object] = {}
    for item in args.param or []:
        if "=" in item:
            key, value = item.split("=", 1)
            params[key] = value
        else:
            params[item] = True
    body: dict[str, float] = {}
    for item in args.body or []:
        _apply_body(body, item)
    try:
        result = runner.run(args.action, params=params or None, body=body or None)
    except (KeyError, RuntimeError) as error:
        _emit({"ok": False, "error": str(error)}, args.json)
        return 1
    _emit(result, args.json)
    return 0 if result["ok"] else 1


def cmd_set_body(args: argparse.Namespace) -> int:
    """Persist instance-level character proportions (state['body'])."""
    runner = _runner(args)
    body: dict[str, float] = {}
    for item in args.body or []:
        _apply_body(body, item)
    try:
        result = runner.set_body(body)
    except RuntimeError as error:
        _emit({"ok": False, "error": str(error)}, args.json)
        return 1
    _emit({"workflow_id": args.workflow, "body": result}, args.json)
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    runner = _runner(args)
    try:
        state = runner.approve(args.action, by=args.by, note=args.note)
    except RuntimeError as error:
        _emit({"ok": False, "error": str(error)}, args.json)
        return 1
    _emit({"action_id": args.action, "approved": True, **state}, args.json)
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    runner = _runner(args)
    try:
        state = runner.reject(args.action, by=args.by, note=args.note)
    except RuntimeError as error:
        _emit({"ok": False, "error": str(error)}, args.json)
        return 1
    _emit({"action_id": args.action, "rejected": True, "status": state["status"], "note": state["note"]}, args.json)
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    runner = _runner(args)
    data = runner.status()
    timeline = []
    for aid, state in data.get("actions", {}).items():
        if isinstance(state, dict) and (state.get("ran_at") or state.get("finished_at")):
            timeline.append({
                "action_id": aid,
                "status": state.get("status"),
                "approved": state.get("approved"),
                "approved_by": state.get("approved_by"),
                "note": state.get("note"),
                "ran_at": state.get("ran_at"),
                "finished_at": state.get("finished_at"),
            })
    _emit(timeline, args.json)
    return 0


def _common_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT, help="Run directory (default: <repo>/run).")
    common.add_argument("--definition-root", type=Path, default=DEFAULT_DEFINITION_ROOT, help="Workflow definitions directory.")
    common.add_argument("--template-root", type=Path, default=DEFAULT_TEMPLATE_ROOT, help="Parameter template directory.")
    common.add_argument("--body-root", type=Path, default=DEFAULT_BODY_ROOT, help="Body (character proportions) template directory.")
    common.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    return common


def build_parser() -> argparse.ArgumentParser:
    common = _common_parser()
    parser = argparse.ArgumentParser(
        prog="workflow",
        description="AssetsLab workflow engine CLI (AI-facing scheduling channel).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", parents=[common], help="List all workflow instances.")
    p.set_defaults(handler=cmd_list)

    p = sub.add_parser("new", parents=[common], help="Create a workflow instance.")
    p.add_argument("--definition", default="default")
    p.add_argument("--id", help="Instance id (defaults to definition id).")
    p.add_argument("--template", help="Industry-style parameter template id (realistic/cartoon/bouncy/heavy/light/...).")
    p.add_argument("--body-template", help="Body (character proportions) template id (standard/chibi/tall/stocky/...).")
    p.add_argument("--body", action="append", metavar="NAME=VALUE",
                   help="Character proportion override (repeatable), e.g. --body head_scale=1.4.")
    p.set_defaults(handler=cmd_new)

    for name in ("status", "next", "history"):
        p = sub.add_parser(name, parents=[common], help=f"{name} for a workflow instance.")
        p.add_argument("--workflow", required=True)
        p.set_defaults(handler={"status": cmd_status, "next": cmd_next, "history": cmd_history}[name])

    p = sub.add_parser("set-body", parents=[common], help="Persist instance-level character proportions.")
    p.add_argument("--workflow", required=True)
    p.add_argument("--body", action="append", metavar="NAME=VALUE", required=True,
                   help="Character proportion to set (repeatable), e.g. --body head_scale=1.4.")
    p.set_defaults(handler=cmd_set_body)

    for name in ("run", "approve", "reject"):
        p = sub.add_parser(name, parents=[common], help=f"{name} an action of a workflow instance.")
        p.add_argument("--workflow", required=True)
        p.add_argument("--action", required=True, help="action_id, e.g. skeleton.front.")
        if name == "run":
            p.add_argument("--param", action="append", metavar="NAME=VALUE",
                           help="Motion knob for the action (repeatable), e.g. --param stride=1.2 --param pelvis_bob=1.5.")
            p.add_argument("--body", action="append", metavar="NAME=VALUE",
                           help="Character proportion override for this run only (repeatable), e.g. --body head_scale=1.6.")
        if name in ("approve", "reject"):
            p.add_argument("--by", default="cli", help="Who approves/rejects (e.g. ai, human).")
            p.add_argument("--note", help="Review note.")
        p.set_defaults(handler={"run": cmd_run, "approve": cmd_approve, "reject": cmd_reject}[name])

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
