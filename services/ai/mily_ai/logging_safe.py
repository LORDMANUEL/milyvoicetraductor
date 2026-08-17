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


def close_logger(logger: logging.Logger) -> None:
    """Cierra y desacopla handlers para liberar el archivo de log también en Windows."""
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.flush()
        finally:
            handler.close()


def build_logger(log_dir: Path, level: str = "info") -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("milyvoice.ai")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    # create_app puede recrearse en tests o reinicios internos. Nunca conservamos un
    # FileHandler apuntando a un directorio temporal/antiguo.
    close_logger(logger)
    handler = RotatingFileHandler(
        log_dir / "ai-engine.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=4,
        encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(SanitizingFormatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger
