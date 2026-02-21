"""
app/logger.py
─────────────
Configures a rotating file + console logger used across the app.
Import `logger` from this module everywhere.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from app.config import Config


def setup_logger(name: str = "medical_chatbot") -> logging.Logger:
    """Create and return a configured logger."""
    os.makedirs(Config.LOG_DIR, exist_ok=True)

    log = logging.getLogger(name)
    log.setLevel(getattr(logging, Config.LOG_LEVEL, logging.INFO))

    # Prevent duplicate handlers when called multiple times
    if log.handlers:
        return log

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s — %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Rotating file handler (5 MB × 3 backups) ────────────────────────────────
    fh = RotatingFileHandler(
        Config.LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)

    # ── Console handler ──────────────────────────────────────────────────────────
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)

    log.addHandler(fh)
    log.addHandler(ch)
    return log


logger = setup_logger()
