"""Logging rotativo sencillo que sanitiza antes de persistir."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .security import sanitize_text


class SanitizingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original_msg, original_args = record.msg, record.args
        try:
            record.msg = sanitize_text(record.getMessage())
            record.args = ()
            return super().format(record)
        finally:
            record.msg, record.args = original_msg, original_args


def build_logger(log_dir: Path, level: str = "info") -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("milyvoice.ai")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    if logger.handlers:
        return logger
    handler = RotatingFileHandler(log_dir / "ai-engine.log", maxBytes=2 * 1024 * 1024, backupCount=4, encoding="utf-8")
    handler.setFormatter(SanitizingFormatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger
