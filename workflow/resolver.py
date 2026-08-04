"""Executable resolution for the workflow engine (cross-platform).

Reuses the verified resolution rules in ``tools/godot_runner.py`` so the
workflow engine behaves identically to the existing automation.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def python_executable(requested: str | None = None) -> str:
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    from godot_runner import resolve_python

    return resolve_python(requested)


def godot_executable(requested: str | None = None) -> str:
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    from godot_runner import resolve_godot

    return resolve_godot(requested)
