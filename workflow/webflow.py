"""Webflow artifact management: infer the GitHub repo and fetch the built
frontend (``workflow/web/dist``) from a GitHub Release when the local build is
missing.

Shared by the CLI (``workflow update``) and the preview server
(``lan_preview_server.py --webflow-*``), so both channels update from the same
build artifact (``webflow-dist.zip``, produced by the GitHub Actions pipeline).
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


def infer_repo(repo_root: Path) -> str | None:
    """Infer owner/repo from git remote origin (ssh or https)."""
    try:
        out = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=repo_root, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        for sep in ("github.com:", "github.com/"):
            if sep in out:
                rest = out.split(sep, 1)[1].removesuffix(".git").strip("/")
                if "/" in rest:
                    return rest
    except Exception:
        pass
    return None


def platform_tag() -> str:
    """Return the release-asset platform tag (linux / macos / windows)."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def download_release_asset(repo: str, version: str | None, asset_name: str, dest: Path,
                           token: str | None = None, log=print) -> Path | None:
    """Download a GitHub Release asset (by name) and extract it into ``dest``.

    Returns the dest dir on success, None on failure. ``version`` is a release
    tag (None/latest = newest release)."""
    try:
        api = f"https://api.github.com/repos/{repo}/releases/{version or 'latest'}"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "assetslab",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        with urllib.request.urlopen(urllib.request.Request(api, headers=headers), timeout=30) as resp:
            release = json.loads(resp.read().decode("utf-8"))
        asset = next((a for a in release.get("assets", []) if a.get("name") == asset_name), None)
        if not asset:
            log(f"[webflow] release {release.get('tag_name', '?')} has no {asset_name} asset")
            return None
        log(f"[webflow] downloading {asset['browser_download_url']}")
        dl = urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "assetslab"})
        with urllib.request.urlopen(dl, timeout=180) as resp:
            data = resp.read()
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(dest)
        log(f"[webflow] extracted {len(data)} bytes into {dest}")
        return dest
    except urllib.error.HTTPError as error:
        log(f"[webflow] GitHub download failed: HTTP {error.code} {error.reason}")
    except Exception as error:
        log(f"[webflow] GitHub download failed: {error}")
    return None


def ensure_webflow_dist(repo_root: Path, repo: str | None = None, version: str | None = None,
                        token: str | None = None, log=print) -> Path | None:
    """Return a usable ``workflow/web/dist``, downloading the ``webflow-dist.zip``
    asset from a GitHub Release when the local build is missing.

    ``repo`` defaults to the git remote origin; ``version`` is a release tag
    (None/latest = newest release). ``token`` is an optional GitHub PAT for
    private repos / rate limits. Returns None if nothing usable is available.
    """
    dist = repo_root / "workflow" / "web" / "dist"
    if dist.is_dir() and (dist / "index.html").is_file():
        return dist
    repo = repo or infer_repo(repo_root)
    if not repo:
        log("[webflow] no local dist and could not infer GitHub repo")
        return None
    download_release_asset(repo, version, "webflow-dist.zip", dist, token, log)
    if (dist / "index.html").is_file():
        return dist
    return None


def read_version(dist: Path) -> dict:
    """Read the CI-written ``version.json`` from a dist build (empty dict if absent)."""
    version_path = dist / "version.json"
    if not version_path.is_file():
        return {}
    try:
        return json.loads(version_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
