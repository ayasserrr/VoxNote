"""Structured-ish logging configuration."""

from __future__ import annotations

import logging
import sys

from app.config import settings

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(settings.log_level.upper())
    for noisy in ("httpx", "httpcore", "fontTools", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _configured = True
