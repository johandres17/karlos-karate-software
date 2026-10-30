"""Regenerate src/karlos_core/_build_info.py from the current git HEAD.

Run before every PyInstaller build (CI does it automatically) so the
Export Build column in reports traces back to the exact source commit.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src" / "karlos_core" / "_build_info.py"


def main() -> None:
    commit = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
    ).strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    TARGET.write_text(
        "# Auto-generated before each PyInstaller build to keep Export Build accurate.\n"
        f"BUILD_COMMIT = '{commit}'\n"
        f"BUILD_TIMESTAMP = '{timestamp}'\n",
        encoding="utf-8",
    )
    print(f"{TARGET.relative_to(ROOT)}: {commit} @ {timestamp}")


if __name__ == "__main__":
    main()
