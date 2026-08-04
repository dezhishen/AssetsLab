"""Per-workflow persistent state with cross-platform locking and atomic writes.

Layout::

    run/
    └── workflows/
        └── <workflow_id>/
            ├── state.json     # single source of truth, actions keyed by action_id
            ├── .lock          # per-workflow_id advisory lock
            └── steps/
                └── <action_id>/   # local image outputs + run.log
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class FileLock:
    """Cross-platform advisory file lock (fcntl on POSIX, msvcrt on Windows)."""

    def __init__(self, path: Path):
        self.path = path
        self._file: Any = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("a+")
        self._file.seek(0, os.SEEK_END)
        if self._file.tell() == 0:
            # msvcrt.locking needs an existing byte region to lock.
            self._file.write("\0")
            self._file.flush()
        self._file.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self._file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX)

    def release(self) -> None:
        if self._file is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        finally:
            self._file.close()
            self._file = None

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.release()


class Store:
    """Read/write ``state.json`` for one workflow instance."""

    def __init__(self, root: Path, workflow_id: str):
        self.root = root.resolve()
        self.workflow_id = workflow_id
        self.dir = self.root / "workflows" / workflow_id
        self.state_path = self.dir / "state.json"
        self.lock_path = self.dir / ".lock"

    def exists(self) -> bool:
        return self.state_path.exists()

    def load(self) -> dict[str, Any]:
        if not self.state_path.exists():
            raise FileNotFoundError(f"workflow instance not found: {self.workflow_id}")
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def save(self, state: dict[str, Any]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = now_iso()
        state["version"] = int(state.get("version", 0)) + 1
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self.state_path)

    @contextmanager
    def lock(self) -> Iterator[None]:
        with FileLock(self.lock_path):
            yield

    def steps_dir(self, action_id: str) -> Path:
        return self.dir / "steps" / action_id
