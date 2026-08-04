#!/usr/bin/env python3
"""PyInstaller entry point for the webflow CLI binary.

Packaged as ``webflow-cli-<platform>.zip`` by the GitHub Actions pipeline;
also usable directly: ``python scripts/webflow_cli.py list``.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workflow.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
