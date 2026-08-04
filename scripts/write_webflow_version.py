#!/usr/bin/env python3
"""Write ``version.json`` into the built frontend dist (CI, cross-platform).

Called by the GitHub Actions pipeline after ``pnpm build``. Uses only stdlib so
it runs on ubuntu / macos / windows the same way.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

root = Path(os.environ.get("GITHUB_WORKSPACE", Path(__file__).resolve().parents[1]))
pkg = json.loads((root / "workflow" / "web" / "package.json").read_text(encoding="utf-8"))
info = {
    "package_version": pkg.get("version", "0.0.0"),
    "commit": os.environ.get("GITHUB_SHA", ""),
    "branch": os.environ.get("GITHUB_REF_NAME", ""),
    "ref": os.environ.get("GITHUB_REF", ""),
    "release_tag": os.environ.get("GITHUB_REF_NAME", "").lstrip("v"),
    "build_time": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    "repo": os.environ.get("GITHUB_REPOSITORY", ""),
}
out = root / "workflow" / "web" / "dist" / "version.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
print(f"wrote {out}")
