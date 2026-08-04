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

from .model import WorkflowDef
from .runner import WorkflowRunner
from .store import Store, now_iso

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_ROOT = ROOT / "run"
DEFAULT_DEFINITION_ROOT = ROOT / "workflow" / "definitions"


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
    workflows_dir = args.run_root / "workflows"
    items: list[dict[str, object]] = []
    if workflows_dir.is_dir():
        for child in sorted(workflows_dir.iterdir()):
            state = child / "state.json"
            if state.exists():
                data = json.loads(state.read_text(encoding="utf-8"))
                actions = data.get("actions", {})
                total = len(actions)
                passed = sum(1 for v in actions.values() if v.get("status") == "passed")
                items.append({
                    "workflow_id": child.name,
                    "definition_id": data.get("definition_id"),
                    "updated_at": data.get("updated_at"),
                    "version": data.get("version"),
                    "progress": f"{passed}/{total}",
                })
    _emit(items, args.json)
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    definition = _definition(args.definition_root, args.definition)
    workflow_id = args.id or args.definition
    store = _store(args.run_root, workflow_id)
    if store.exists():
        raise SystemExit(f"workflow instance already exists: {workflow_id}")
    state = {
        "schema": "assetslab_workflow_v1",
        "workflow_id": workflow_id,
        "definition_id": definition.definition_id,
        "title": definition.title,
        "created_at": now_iso(),
        "version": 0,
        "actions": {a.action_id: {"status": "pending", "approved": False, "outputs": []} for a in definition.actions},
    }
    with store.lock():
        store.save(state)
    _emit({"workflow_id": workflow_id, "created": True, "next": _first_pending(definition)}, args.json)
    return 0


def _first_pending(definition: WorkflowDef) -> str | None:
    return definition.actions[0].action_id if definition.actions else None


def cmd_status(args: argparse.Namespace) -> int:
    runner = _runner(args)
    data = runner.status()
    data["next"] = runner.next()
    # Enrich each action with definition metadata (phase/title) so the Web
    # console can group and label actions. This is output-only; state.json
    # keeps only the runtime state.
    try:
        definition = _definition(args.definition_root, data.get("definition_id", "default"))
        for aid, state in data.get("actions", {}).items():
            action = definition.by_id(aid)
            if action and isinstance(state, dict):
                state["phase"] = action.phase
                state["title"] = action.title
    except Exception:
        pass
    _emit(data, args.json)
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
    try:
        result = runner.run(args.action, params=params or None)
    except (KeyError, RuntimeError) as error:
        _emit({"ok": False, "error": str(error)}, args.json)
        return 1
    _emit(result, args.json)
    return 0 if result["ok"] else 1


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
    p.set_defaults(handler=cmd_new)

    for name in ("status", "next", "history"):
        p = sub.add_parser(name, parents=[common], help=f"{name} for a workflow instance.")
        p.add_argument("--workflow", required=True)
        p.set_defaults(handler={"status": cmd_status, "next": cmd_next, "history": cmd_history}[name])

    for name in ("run", "approve", "reject"):
        p = sub.add_parser(name, parents=[common], help=f"{name} an action of a workflow instance.")
        p.add_argument("--workflow", required=True)
        p.add_argument("--action", required=True, help="action_id, e.g. skeleton.front.legs.")
        if name == "run":
            p.add_argument("--param", action="append", metavar="NAME=VALUE",
                           help="Tunable knob for the action (repeatable), e.g. --param stride=1.2 --param pelvis_bob=1.5.")
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
