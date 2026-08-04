#!/usr/bin/env python3
"""Cross-platform workflow engine CLI entry point.

Usage examples (AI / human scheduling):
    python tools/workflow.py list
    python tools/workflow.py new --definition default --id review-a
    python tools/workflow.py status --workflow review-a --json
    python tools/workflow.py next --workflow review-a
    python tools/workflow.py run --workflow review-a --action skeleton.front.legs --json
    python tools/workflow.py approve --workflow review-a --action skeleton.front.legs --by ai --note "ok"
    python tools/workflow.py reject --workflow review-a --action skeleton.front.legs --by human --note "redraw leg"
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workflow.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
