"""Resource path resolution for KARLOS ANNOTATOR.

Works both in development (running from source) and when frozen
with PyInstaller (onedir or onefile), where data files are extracted
to ``sys._MEIPASS`` (onefile) or placed next to the executable (onedir).
"""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    """Return the absolute path to a bundled resource.

    Args:
        *parts: Path components relative to the project root,
            e.g. ``resource_path("karlos_core", "resources", "icons", "karate.png")``.

    Returns:
        Absolute ``Path`` to the resource, valid in dev and frozen modes.
    """
    if getattr(sys, "frozen", False):
        # PyInstaller: onefile extracts to _MEIPASS; onedir sets it to the
        # app's directory ("_internal" in modern PyInstaller).
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidate = base.joinpath(*parts)
        if candidate.exists():
            return candidate
        # Fallback: next to the executable (onedir layouts)
        alt = Path(sys.executable).parent.joinpath(*parts)
        if alt.exists():
            return alt
        return candidate
    # Development: project root is two levels above this file
    # (utils/ -> karlos_core/ -> project root)
    root = Path(__file__).resolve().parent.parent.parent
    return root.joinpath(*parts)


def icons_dir() -> Path:
    """Return the directory containing the sport icon PNGs."""
    return resource_path("karlos_core", "resources", "icons")
