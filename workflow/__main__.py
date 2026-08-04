"""Enable ``python -m workflow <command>`` as the cross-platform CLI entry point.

Replaces the old ``tools/workflow.py`` shim so no external script file is
needed; the SDK's CLI lives inside the package.
"""

from __future__ import annotations

from workflow.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
