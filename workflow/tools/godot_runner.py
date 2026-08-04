"""Cross-platform core helpers for AssetsLab automation.

Resolves the Godot and Python executables and builds the headless Godot
argument list.  Used by the assetslab CLI and the workflow engine so the same
rules run on Windows, Linux and macOS.  On Windows a ``*_console.exe`` build is
required for silent automation; on Linux/macOS the single binary runs with
``--headless``.

Path conventions:

- ``tools/godot_runner.py`` resolves every path relative to this repository
  root (``ROOT``), so it can be invoked from anywhere.
- Generated artifacts are written under ``prototype/test_output/`` (git
  ignored); the skeleton pipeline writes under
  ``prototype/test_output/skeleton_pipeline/``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOTYPE_ROOT = ROOT / "prototype"
TEST_OUTPUT = PROTOTYPE_ROOT / "test_output"
SKELETON_PIPELINE = TEST_OUTPUT / "skeleton_pipeline"
PREVIEW_ROOT = PROTOTYPE_ROOT / "preview"
PREVIEW_ASSETS = PREVIEW_ROOT / "assets"
PYTHON_MODULES = ROOT / ".tools" / "python"

IS_WINDOWS = os.name == "nt"


class ResolutionError(RuntimeError):
    """Raised when a required executable cannot be resolved."""


# ------------------------------------------------------------------ python --


def resolve_python(requested: str | None = None) -> str:
    """Resolve the Python executable used by the asset toolchain.

    Resolution order:
    ``--python`` / ``PYTHON_BIN`` -> local ``.venv`` -> ``PATH``.
    """
    value = requested or os.environ.get("PYTHON_BIN")
    if value:
        found = shutil.which(value)
        if found:
            return found
        path = Path(value).expanduser()
        if path.is_file():
            return str(path)
        raise ResolutionError(
            f"Python executable was not found at '{value}'. Set PYTHON_BIN or pass --python."
        )

    candidates: list[Path] = []
    if IS_WINDOWS:
        candidates = [ROOT / ".venv" / "Scripts" / "python.exe"]
    else:
        candidates = [
            ROOT / ".venv" / "bin" / "python",
            ROOT / ".venv" / "bin" / "python3",
        ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    for name in ("python", "python3", "py"):
        found = shutil.which(name)
        if found:
            return found

    raise ResolutionError(
        "Python executable was not found. Set PYTHON_BIN, pass --python, or add Python to PATH."
    )


# ------------------------------------------------------------------ godot --


def _console_sibling(path: Path) -> Path | None:
    """On Windows, prefer the ``*_console.exe`` sibling of a GUI build.

    Automated capture must never launch the GUI binary (it can open a window
    despite a caller intending a silent run).  Mirrors ``Resolve-HeadlessGodotPath``.
    """
    if path.name.endswith("_console.exe"):
        return path
    console = path.with_name(path.stem + "_console.exe")
    if console.is_file():
        return console
    siblings = list(path.parent.glob("*_console.exe"))
    if len(siblings) == 1:
        return siblings[0]
    return None


def _godot_from_env(requested: str | None) -> str | None:
    value = requested or os.environ.get("GODOT_BIN") or os.environ.get("GODOT_PATH")
    if not value:
        return None
    found = shutil.which(value)
    if found:
        return found
    path = Path(value).expanduser()
    if path.is_file():
        return str(path)
    raise ResolutionError(
        f"Godot executable was not found at '{value}'. Set GODOT_BIN/GODOT_PATH or pass --godot."
    )


def _godot_from_path() -> str | None:
    for name in ("godot4", "godot"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _godot_adjacent() -> str | None:
    """Look next to the repository for a Godot 4.7 install."""
    base = ROOT.parent / "Godot-4.7"
    if not base.is_dir():
        return None
    if IS_WINDOWS:
        exe = base / "unpacked" / "Godot_v4.7-stable_win64_console.exe"
        if exe.is_file():
            return str(exe)
    else:
        # Linux/macOS ship a single executable (no console variant).
        for child in base.rglob("*"):
            if (
                child.is_file()
                and os.access(child, os.X_OK)
                and ("godot" in child.name.lower() or "x86_64" in child.name.lower())
            ):
                return str(child)
    return None


def resolve_godot(requested: str | None = None) -> str:
    """Resolve a Godot executable and require a headless-capable build.

    Resolution order:
    ``--godot`` / ``GODOT_BIN`` / ``GODOT_PATH`` -> ``PATH`` (godot4, godot)
    -> adjacent ``Godot-4.7`` install.  On Windows, the ``*_console.exe``
    build is always preferred so capture never opens a window.
    """
    raw = _godot_from_env(requested) or _godot_from_path() or _godot_adjacent()
    if not raw:
        raise ResolutionError(
            "Godot executable was not found. Set GODOT_BIN/GODOT_PATH, pass --godot, "
            "or add Godot to PATH."
        )
    resolved = Path(raw)
    if IS_WINDOWS:
        console = _console_sibling(resolved)
        if console is None:
            raise ResolutionError(
                "Silent Godot automation on Windows requires a *_console.exe executable. "
                "No unambiguous console sibling was found."
            )
        return str(console)
    return str(resolved)


def godot_base_args(
    script: str | None = None,
    log_file: Path | None = None,
    fixed_fps: int | None = None,
) -> list[str]:
    """Build the common headless Godot argument list (platform-aware)."""
    args = ["--headless"]
    if IS_WINDOWS:
        # The PowerShell scripts pass the windows display driver explicitly;
        # on Linux/macOS --headless already selects a silent display driver.
        args += ["--display-driver", "windows"]
    args += [
        "--rendering-driver", "opengl3",
        "--rendering-method", "gl_compatibility",
        "--audio-driver", "Dummy",
        "--path", str(PROTOTYPE_ROOT),
    ]
    if script:
        args += ["--script", script]
    if log_file:
        args += ["--log-file", str(log_file)]
    if fixed_fps is not None:
        args += ["--fixed-fps", str(fixed_fps)]
    return args


# ------------------------------------------------------------------- misc --


def python_env() -> dict:
    """Return a copy of the environment with the toolchain PYTHONPATH set."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PYTHON_MODULES)
    return env


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a command, capturing combined stdout/stderr for diagnostics."""
    process = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    if check and process.returncode != 0:
        output = (process.stdout or "") + (process.stderr or "")
        raise RuntimeError(
            f"Command failed with exit code {process.returncode}: "
            f"{' '.join(map(str, command))}\n{output}"
        )
    return process
