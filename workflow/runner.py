"""Execute and approve workflow actions, delegating to the assetslab executor.

Each action runs as a subprocess of the cross-platform CLI, so the workflow
engine never re-implements pipeline logic.  Action outputs are local files
(PNG/GIF/log) collected into ``run/workflows/<id>/steps/<action_id>/`` so both
AI (via absolute paths) and the Web console (via HTTP) can inspect them.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .model import ActionDef, ActionState, Approval, Status, WorkflowDef
from .store import Store, now_iso


class WorkflowRunner:
    def __init__(self, root: Path, definition: WorkflowDef, workflow_id: str, store: Store):
        self.root = root.resolve()
        self.definition = definition
        self.workflow_id = workflow_id
        self.store = store
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
        return state.status == Status.PASSED.value and state.approved

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

    # -------------------------------------------------------- transitions --

    def approve(self, action_id: str, by: str = "cli", note: str | None = None) -> dict[str, Any]:
        action = self._require(action_id)
        with self.store.lock():
            actions = self._state_actions()
            state = self._action_state(actions, action_id)
            if state.status != Status.PASSED.value:
                raise RuntimeError(f"action {action_id} is not passed (status={state.status}); cannot approve")
            state.approved = True
            state.approved_by = by
            state.note = note
            actions[action_id] = state
            self._save_actions(actions)
        return state.to_dict()

    def reject(self, action_id: str, by: str = "cli", note: str | None = None) -> dict[str, Any]:
        """Reject an action and send it back to pending so it can be redone."""
        self._require(action_id)
        with self.store.lock():
            actions = self._state_actions()
            state = self._action_state(actions, action_id)
            if state.status not in (Status.PASSED.value, Status.FAILED.value):
                raise RuntimeError(f"action {action_id} has nothing to reject (status={state.status})")
            state.status = Status.PENDING.value
            state.approved = False
            state.approved_by = None
            state.note = note
            actions[action_id] = state
            self._save_actions(actions)
        return state.to_dict()

    def run(self, action_id: str, params: dict | None = None) -> dict[str, Any]:
        """Run one action, collect outputs, verify the gate, update state.

        ``params`` override the tunable knobs declared in the action definition
        (e.g. stride / pelvis_bob / arm_swing).  ``{name}`` placeholders in the
        exec list are replaced by the resolved value, so the same action can be
        re-run with different parameters and the used values are recorded in
        the action state for review.
        """
        action = self._require(action_id)
        resolved = self._resolve_params(action, params)
        step_dir = self.store.steps_dir(action_id)

        with self.store.lock():
            actions = self._state_actions()
            for dep in action.depends:
                if not self._done(actions, dep):
                    raise RuntimeError(f"dependency not satisfied: {dep}")
            state = self._action_state(actions, action_id)
            state.status = Status.RUNNING.value
            state.ran_at = now_iso()
            state.params = resolved
            actions[action_id] = state
            self._save_actions(actions)
            step_dir.mkdir(parents=True, exist_ok=True)

        # Long-running subprocess runs outside the lock.
        log_path = step_dir / "run.log"
        # Expand {workflow_id} and {param} placeholders so exec can target
        # dist/<workflow_id>/ and accept tunable knobs.
        expanded_exec = self._expand_exec(action, resolved)
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
        outputs: list[str] = []
        for rel in action.collect:
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
            state.outputs = outputs
            state.finished_at = now_iso()
            state.status = Status.PASSED.value if ok else Status.FAILED.value
            if ok and action.approval == Approval.AUTO.value:
                state.approved = True
                state.approved_by = "auto"
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
        """Merge declared defaults with the run-time overrides."""
        resolved: dict[str, Any] = {}
        for name, spec in action.params.items():
            if isinstance(spec, dict):
                resolved[name] = spec.get("default")
            else:
                resolved[name] = spec
        for name, value in (overrides or {}).items():
            resolved[name] = value
        return resolved

    def _expand_exec(self, action: ActionDef, params: dict) -> list[str]:
        """Replace {workflow_id} and {param} placeholders in the exec list."""
        out: list[str] = []
        for part in action.exec:
            part = part.replace("{workflow_id}", self.workflow_id)
            for name, value in params.items():
                part = part.replace("{" + name + "}", "" if value is None else str(value))
            out.append(part)
        return out
