from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from build_preview_assets import main as build_preview_assets


ROOT = Path(__file__).resolve().parents[1]
PREVIEW_ROOT = ROOT / "prototype/preview"
CURRENT_ASSETS = PREVIEW_ROOT / "assets"


def safe_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_" else "_" for char in value)
    return cleaned.strip("_") or "snapshot"


def write_snapshot_page(snapshot_root: Path, snapshot_name: str) -> None:
    page = (PREVIEW_ROOT / "index.html").read_text(encoding="utf-8")
    page = page.replace("assets/", "")
    page = page.replace("AssetsLab Preview", f"AssetsLab Preview {snapshot_name}")
    (snapshot_root / "index.html").write_text(page, encoding="utf-8")


def publish_snapshot(name: str | None) -> tuple[str, Path]:
    build_preview_assets()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    snapshot_name = f"{stamp}-{safe_name(name)}" if name else stamp
    snapshot_root = PREVIEW_ROOT / "snapshots" / snapshot_name
    snapshot_root.mkdir(parents=True, exist_ok=False)
    for source_path in CURRENT_ASSETS.rglob("*"):
        if not source_path.is_file() or source_path.suffix == ".import":
            continue
        destination = snapshot_root / source_path.relative_to(CURRENT_ASSETS)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
    manifest = json.loads((CURRENT_ASSETS / "current_preview_manifest.json").read_text(encoding="utf-8"))
    manifest["snapshot"] = snapshot_name
    manifest["created_at"] = datetime.now().isoformat(timespec="seconds")
    (snapshot_root / "snapshot_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_snapshot_page(snapshot_root, snapshot_name)
    return snapshot_name, snapshot_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish the current-only AssetsLab preview snapshot.")
    parser.add_argument("--name", help="Optional English snapshot label")
    args = parser.parse_args()
    snapshot_name, snapshot_root = publish_snapshot(args.name)
    print(f"PREVIEW_SNAPSHOT_PASS name={snapshot_name}")
    print(f"PREVIEW_SNAPSHOT_PATH={snapshot_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
