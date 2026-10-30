"""Central file logging for KARLOS ANNOTATOR.

Writes a rotating log to ~/.karlos_annotator/logs/karlos.log so failures
on end-user machines can be diagnosed from the log file instead of
screenshots. Call setup_logging() once from main(); use
get_logger(__name__) everywhere else.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from karlos_core.identidad import CARPETA_POR_DEFECTO

LOG_DIR = CARPETA_POR_DEFECTO / "logs"   # la edición pone la suya (decisión 0006)
LOG_FILE = LOG_DIR / "karlos.log"

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger once: rotating file + stderr."""
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError:
        # Logging must never block the app (e.g. read-only home dir).
        pass

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(fmt)
    root.addHandler(stream_handler)

    # Windowed builds (.exe / .app) have no console: without this an
    # uncaught exception kills the app with no trace anywhere.
    def _excepthook(exc_type, exc, tb):
        logging.getLogger("uncaught").critical(
            "Unhandled exception", exc_info=(exc_type, exc, tb)
        )
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook


def get_logger(name: str) -> logging.Logger:
    """Return a module logger (thin alias for logging.getLogger)."""
    return logging.getLogger(name)
