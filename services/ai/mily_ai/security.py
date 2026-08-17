"""Emparejamiento local y sanitización reutilizable de datos operativos."""

from __future__ import annotations

import os
import re
import secrets
from pathlib import Path

_SECRET_PATTERNS = [
    re.compile(r"(?i)\b(token|password|secret|api[_-]?key)\s*[=:]\s*[^\s,;]+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
]
_WINDOWS_USER_PATH = re.compile(r"(?i)[A-Z]:\\Users\\[^\\\s]+")
_UNIX_USER_PATH = re.compile(r"/(?:home|Users)/[^/\s]+")


def sanitize_text(value: object) -> str:
    """Elimina secretos y nombres de usuario de una cadena antes de loguearla."""
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: f"{m.group(1) if m.lastindex else 'secret'}=<REDACTED>", text)
    text = _WINDOWS_USER_PATH.sub("<USER_PATH>", text)
    text = _UNIX_USER_PATH.sub("<USER_PATH>", text)
    return text[:4000]


class PairingTokenService:
    """Genera un token local persistente; nunca lo escribe en logs."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def get_or_create(self) -> str:
        if self.path.exists():
            token = self.path.read_text(encoding="utf-8").strip()
            if len(token) >= 40:
                return token
        self.path.parent.mkdir(parents=True, exist_ok=True)
        token = secrets.token_urlsafe(36)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(token, encoding="utf-8")
        try:
            os.chmod(temp, 0o600)
        except OSError:
            pass
        temp.replace(self.path)
        return token
