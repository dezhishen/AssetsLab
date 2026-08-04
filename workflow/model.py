"""Workflow data model: declarative action definitions and per-instance state.

The workflow is decomposed into stable, flat ``action_id`` entries (e.g.
``skeleton.front``).  A ``WorkflowDef`` is the template; per-run state is
persisted per ``workflow_id`` by :mod:`workflow.store`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Status(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Approval(str, Enum):
    """auto: passed by the automatic gate; human: needs approve/reject."""

    AUTO = "auto"
    HUMAN = "human"


@dataclass
class ActionDef:
    """Declarative description of one workflow action."""

    action_id: str
    title: str
    phase: str
    exec: list[str] = field(default_factory=list)        # assetslab.py sub-command, e.g. ["stage","front","legs"]
    depends: list[str] = field(default_factory=list)     # action_ids that must pass+approve first
    collect: list[str] = field(default_factory=list)     # repo-relative outputs copied into the run step dir
    approval: str = Approval.HUMAN.value
    description: str = ""
    params: dict = field(default_factory=dict)           # tunable knobs: name -> {default,min,max,label}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionDef":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ActionState:
    """Per-instance runtime state of an action."""

    status: str = Status.PENDING.value
    approved: bool = False
    approved_by: str | None = None
    note: str | None = None
    outputs: list[str] = field(default_factory=list)     # absolute paths to local images/files
    ran_at: str | None = None
    finished_at: str | None = None
    params: dict = field(default_factory=dict)           # params used for the last run

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionState":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowDef:
    """A workflow template loaded from workflow/definitions/<id>.json."""

    definition_id: str
    title: str
    actions: list[ActionDef]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowDef":
        return cls(
            definition_id=data["definition_id"],
            title=data.get("title", data["definition_id"]),
            actions=[ActionDef.from_dict(a) for a in data["actions"]],
        )

    @classmethod
    def load(cls, path: str | Path) -> "WorkflowDef":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def by_id(self, action_id: str) -> ActionDef | None:
        for action in self.actions:
            if action.action_id == action_id:
                return action
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition_id": self.definition_id,
            "title": self.title,
            "actions": [a.to_dict() for a in self.actions],
        }
