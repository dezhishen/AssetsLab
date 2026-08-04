#!/usr/bin/env python3
"""PyInstaller entry point for the webflow server binary.

Packaged as ``webflow-server-<platform>.zip`` by the GitHub Actions pipeline;
also usable directly: ``python scripts/webflow_server.py --port 8765 --directory prototype/preview``.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workflow.tools.lan_preview_server import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
