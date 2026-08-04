"""Execute workflow actions, delegating to the assetslab executor.

Each action runs as a subprocess of the cross-platform CLI, so the workflow
engine never re-implements pipeline logic.  Action outputs are local files
(PNG/GIF/log) collected into ``run/workflows/<id>/steps/<action_id>/`` so both
AI (via absolute paths) and the Web console (via HTTP) can inspect them.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .model import ActionDef, ActionState, BODY_NAMES, Status, WorkflowDef, default_body
from .store import Store, now_iso


# ------------------------------------------------------------ instances --
# Instance-level operations (list / create) are shared by the CLI and the Web
# API: both channels drive the SDK directly, they do NOT depend on each other.

def list_instances(root: Path, run_root: Path) -> list[dict]:
    """All workflow instances with progress (shared by CLI and Web API)."""
    workflows_dir = run_root / "workflows"
    items: list[dict] = []
    if workflows_dir.is_dir():
        for child in sorted(workflows_dir.iterdir()):
            state_path = child / "state.json"
            if state_path.exists():
                data = json.loads(state_path.read_text(encoding="utf-8"))
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
    return items


def create_instance(root: Path, run_root: Path, workflow_id: str, definition_id: str = "default",
                    template_id: str | None = None, body_template: str | None = None,
                    body: dict | None = None,
                    definitions_root: Path | None = None, templates_root: Path | None = None,
                    body_root: Path | None = None) -> dict:
    """Create a workflow instance (shared by CLI and Web API)."""
    definitions_root = definitions_root or (root / "workflow" / "definitions")
    templates_root = templates_root or (root / "workflow" / "templates")
    body_root = body_root or (root / "workflow" / "body")
    path = definitions_root / f"{definition_id}.json"
    if not path.exists():
        raise KeyError(f"definition not found: {definition_id} ({path})")
    definition = WorkflowDef.load(path)
    store = Store(run_root, workflow_id)
    if store.exists():
        raise RuntimeError(f"workflow instance already exists: {workflow_id}")
    template_params: dict[str, float] = {}
    if template_id:
        tpl = json.loads((templates_root / f"{template_id}.json").read_text(encoding="utf-8"))
        template_params = {k: float(v) for k, v in (tpl.get("params") or {}).items()}
    body_values = default_body()
    if body_template:
        body_tpl = json.loads((body_root / f"{body_template}.json").read_text(encoding="utf-8"))
        body_values.update({k: float(v) for k, v in (body_tpl.get("body") or {}).items() if k in BODY_NAMES})
    for name, value in (body or {}).items():
        if name not in BODY_NAMES:
            raise RuntimeError(f"unknown body proportion: {name} (known: {', '.join(BODY_NAMES)})")
        body_values[name] = float(value)
    state = {
        "schema": "assetslab_workflow_v1",
        "workflow_id": workflow_id,
        "definition_id": definition.definition_id,
        "title": definition.title,
        "template_id": template_id,
        "template_params": template_params,
        "body_template": body_template,
        "body": body_values,
        "created_at": now_iso(),
        "version": 0,
        "actions": {a.action_id: {"status": "pending", "outputs": []} for a in definition.actions},
    }
    with store.lock():
        store.save(state)
    return {"workflow_id": workflow_id, "created": True, "template": template_id,
            "body": body_values,
            "next": definition.actions[0].action_id if definition.actions else None}


def delete_instance(root: Path, run_root: Path, workflow_id: str, remove_artifacts: bool = False) -> dict:
    """Delete a workflow instance.  Exported artifacts (dist/<id>) are KEPT
    unless ``remove_artifacts`` is true; they can be removed separately via
    :func:`delete_artifacts`."""
    store = Store(run_root, workflow_id)
    if not store.exists():
        raise KeyError(f"workflow instance not found: {workflow_id}")
    store.delete()
    removed_artifacts = False
    if remove_artifacts:
        dist_dir = root / "dist" / workflow_id
        if dist_dir.is_dir():
            shutil.rmtree(dist_dir)
            removed_artifacts = True
    return {"workflow_id": workflow_id, "deleted": True, "removed_artifacts": removed_artifacts}


def delete_artifacts(root: Path, workflow_id: str) -> dict:
    """Delete only the exported artifact package (dist/<id>); keep the instance."""
    dist_dir = root / "dist" / workflow_id
    if not dist_dir.is_dir():
        raise KeyError(f"no exported artifacts for instance: {workflow_id}")
    shutil.rmtree(dist_dir)
    return {"workflow_id": workflow_id, "deleted": True}


class WorkflowRunner:
    def __init__(self, root: Path, definition: WorkflowDef, workflow_id: str, store: Store):
        self.root = root.resolve()
        self.definition = definition
        self.workflow_id = workflow_id
        self.store = store
        if getattr(sys, "frozen", False):
            # A bundled binary cannot re-execute itself as Python. Delegate
            # rendering to a real interpreter (PYTHON_BIN -> .venv -> PATH).
            # The renderer script is preferred from the source tree (cwd, so
            # it can reach prototype/ assets); fall back to the bundled copy.
            renderer = self.root / "workflow" / "tools" / "assetslab.py"
            if not renderer.is_file():
                bundled = Path(getattr(sys, "_MEIPASS", Path.cwd()))
                renderer = bundled / "workflow" / "tools" / "assetslab.py"
            python = os.environ.get("PYTHON_BIN")
            if not python:
                for name in ("python3", "python"):
                    candidate = shutil.which(name)
                    if candidate:
                        python = candidate
                        break
            self._cli = [python, str(renderer)] if python and renderer.is_file() else []
        else:
            self._cli = [sys.executable, str(self.root / "workflow" / "tools" / "assetslab.py")]

    # ------------------------------------------------------------- state --

    def _state_actions(self) -> dict[str, ActionState]:
        data = self.store.load()
        return {aid: ActionState.from_dict(v) for aid, v in data.get("actions", {}).items()}

    def _save_actions(self, actions: dict[str, ActionState]) -> None:
        data = self.store.load()
        data["actions"] = {aid: st.to_dict() for aid, st in actions.items()}
        self.store.save(data)

    @staticmethod
    def _action_state(actions: dict[str, ActionState], action_id: str) -> ActionState:
        return actions.get(action_id) or ActionState()

    def _done(self, actions: dict[str, ActionState], action_id: str) -> bool:
        state = self._action_state(actions, action_id)
        return state.status == Status.PASSED.value

    # ----------------------------------------------------------- queries --

    def next(self) -> str | None:
        """Return the first pending action whose dependencies are satisfied."""
        actions = self._state_actions()
        for action in self.definition.actions:
            state = self._action_state(actions, action.action_id)
            if state.status != Status.PENDING.value:
                continue
            if all(self._done(actions, dep) for dep in action.depends):
                return action.action_id
        return None

    def status(self) -> dict[str, Any]:
        return self.store.load()

    def status_view(self) -> dict[str, Any]:
        """Instance status enriched with the recommended next action and
        per-action phase/title metadata (shared by CLI and Web API)."""
        data = self.status()
        data["next"] = self.next()
        try:
            for aid, st in data.get("actions", {}).items():
                action = self.definition.by_id(aid)
                if action and isinstance(st, dict):
                    st["phase"] = action.phase
                    st["title"] = action.title
        except Exception:
            pass
        return data

    # -------------------------------------------------------- transitions --

    def run(self, action_id: str, params: dict | None = None, body: dict | None = None) -> dict[str, Any]:
        """Run one action, collect outputs, verify the gate, update state.

        ``params`` override the *motion* knobs declared in the action definition
        (stride / pelvis_bob / arm_swing).  ``body`` overrides the instance-level
        *character* proportions (arm_length … height) for this run only; they
        apply to every action so front/side/back stay consistent.  ``{name}``
        placeholders in the exec list are replaced by the resolved value, so the
        same action can be re-run with different parameters and the used values
        are recorded in the action state for inspection.
        """
        action = self._require(action_id)
        resolved = self._resolve_params(action, params)
        body = self._resolve_body(body)
        step_dir = self.store.steps_dir(action_id)

        with self.store.lock():
            actions = self._state_actions()
            for dep in action.depends:
                if not self._done(actions, dep):
                    raise RuntimeError(f"dependency not satisfied: {dep}")
            state = self._action_state(actions, action_id)
            state.status = Status.RUNNING.value
            state.ran_at = now_iso()
            state.params = {**resolved, **body}  # record motion + body knobs used
            actions[action_id] = state
            self._save_actions(actions)
            step_dir.mkdir(parents=True, exist_ok=True)

        # Long-running subprocess runs outside the lock.
        log_path = step_dir / "run.log"
        # Expand {workflow_id}, {motion param} and {body proportion} placeholders
        # so exec can target dist/<workflow_id>/ and accept tunable knobs.
        expanded_exec = self._expand_exec(action, resolved, body)
        try:
            process = subprocess.run(
                self._cli + expanded_exec,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=1800,
            )
            exit_code = process.returncode
            log_path.write_text((process.stdout or "") + (process.stderr or ""), encoding="utf-8")
        except subprocess.TimeoutExpired as error:
            exit_code = -1
            log_path.write_text(f"timeout: {error}\n", encoding="utf-8")

        ok = exit_code == 0

        # Snapshot the previous run's outputs as <name>.prev.<ext> so the web UI
        # can show the last version side-by-side with the current one.  This MUST
        # happen before ``collect`` below, which overwrites the step files with
        # the newly built outputs — otherwise the backup would copy the current
        # build onto itself and prev == current.
        prev_outputs: list[str] = []
        with self.store.lock():
            actions = self._state_actions()
            state = self._action_state(actions, action_id)
            for old in state.outputs:
                old_path = Path(old)
                if old_path.exists() and old_path.parent == step_dir:
                    prev_path = old_path.parent / (old_path.stem + ".prev" + old_path.suffix)
                    try:
                        shutil.copy2(old_path, prev_path)
                        prev_outputs.append(str(prev_path))
                    except OSError:
                        pass

        outputs: list[str] = []
        collect_rel = self._expand_collect(action, resolved, body)
        for rel in collect_rel:
            source = (self.root / rel).resolve()
            if source.exists():
                destination = step_dir / source.name
                shutil.copy2(source, destination)
                outputs.append(str(destination.resolve()))
            elif ok:
                ok = False  # required output missing -> gate failed

        # export.artifacts writes a whole package under dist/<workflow_id>; surface
        # every produced file as an output so AI/Web can inspect and open them.
        if expanded_exec[:1] == ["run-script"] and "export_artifacts.py" in expanded_exec:
            dist_dir = self.root / "dist" / self.workflow_id
            if dist_dir.is_dir():
                outputs += [str(p.resolve()) for p in sorted(dist_dir.rglob("*")) if p.is_file()]

        with self.store.lock():
            actions = self._state_actions()
            state = self._action_state(actions, action_id)
            state.prev_outputs = prev_outputs
            state.outputs = outputs
            state.finished_at = now_iso()
            state.status = Status.PASSED.value if ok else Status.FAILED.value
            actions[action_id] = state
            self._save_actions(actions)

        return {
            "action_id": action_id,
            "ok": ok,
            "exit_code": exit_code,
            "outputs": outputs,
            "log": str(log_path.resolve()),
        }

    def _require(self, action_id: str) -> ActionDef:
        action = self.definition.by_id(action_id)
        if action is None:
            raise KeyError(f"unknown action: {action_id}")
        return action

    # ------------------------------------------------------------- params --

    def _resolve_params(self, action: ActionDef, overrides: dict | None) -> dict:
        """Merge, in priority order: definition defaults < instance template
        (industry-style default knob values chosen at creation) < run-time
        overrides.  Only *motion* knobs declared in ``action.params`` live here;
        character proportions come from :meth:`_resolve_body`."""
        resolved: dict[str, Any] = {}
        for name, spec in action.params.items():
            if isinstance(spec, dict):
                resolved[name] = spec.get("default")
            else:
                resolved[name] = spec
        data = self.store.load()
        for name, value in (data.get("template_params") or {}).items():
            if name in resolved:
                resolved[name] = value
        for name, value in (overrides or {}).items():
            resolved[name] = value
        return resolved

    def _resolve_body(self, overrides: dict | None) -> dict[str, float]:
        """Instance-level character proportions: state['body'] merged with
        run-time --body overrides.  All six proportions are always present so
        ``{name}`` placeholders in exec are always substituted."""
        data = self.store.load()
        body = default_body()
        body.update({k: float(v) for k, v in (data.get("body") or {}).items() if k in BODY_NAMES})
        for name, value in (overrides or {}).items():
            if name in BODY_NAMES:
                body[name] = float(value)
        return body

    def set_body(self, overrides: dict) -> dict[str, float]:
        """Persist instance-level body proportions (merge into state['body'])."""
        if not overrides:
            raise RuntimeError("no body values given")
        with self.store.lock():
            data = self.store.load()
            body = default_body()
            body.update({k: float(v) for k, v in (data.get("body") or {}).items() if k in BODY_NAMES})
            for name, value in overrides.items():
                if name not in BODY_NAMES:
                    raise RuntimeError(f"unknown body proportion: {name} (known: {', '.join(BODY_NAMES)})")
                body[name] = float(value)
            data["body"] = body
            self.store.save(data)
        return body

    def _expand_exec(self, action: ActionDef, params: dict, body: dict | None = None) -> list[str]:
        """Replace {workflow_id}, {motion param} and {body proportion}
        placeholders in the exec list."""
        out: list[str] = []
        for part in action.exec:
            out.append(self._expand_string(part, params, body))
        return out

    def _expand_collect(self, action: ActionDef, params: dict, body: dict | None = None) -> list[str]:
        """Replace the same placeholders in the collect list (so artifact paths
        like dist/{workflow_id}/skins/{skin}_{motion}_{view}.gif resolve)."""
        return [self._expand_string(rel, params, body) for rel in action.collect]

    def _expand_string(self, value: str, params: dict, body: dict | None = None) -> str:
        """Substitute {workflow_id} plus {param}/{body} placeholders in a string."""
        values: dict[str, Any] = dict(params)
        if body:
            values.update(body)
        value = value.replace("{workflow_id}", self.workflow_id)
        for name, val in values.items():
            value = value.replace("{" + name + "}", "" if val is None else str(val))
        return value
