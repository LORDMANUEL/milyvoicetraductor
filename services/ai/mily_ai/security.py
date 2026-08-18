"""Emparejamiento local y sanitización reutilizable de datos operativos."""

from __future__ import annotations

import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

_SECRET_PATTERNS = [
    re.compile(r"(?i)\b(token|password|secret|api[_-]?key)\s*[=:]\s*[^\s,;]+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
]
_WINDOWS_USER_PATH = re.compile(r"(?i)[A-Z]:\\Users\\[^\\\s]+")
_UNIX_USER_PATH = re.compile(r"/(?:home|Users)/[^/\s]+")
MAX_EPHEMERAL_TTL_SECONDS = 300


def sanitize_text(value: object) -> str:
    """Elimina secretos y nombres de usuario de una cadena antes de loguearla."""
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(
            lambda match: f"{match.group(1) if match.lastindex else 'secret'}=<REDACTED>",
            text,
        )
    text = _WINDOWS_USER_PATH.sub("<USER_PATH>", text)
    text = _UNIX_USER_PATH.sub("<USER_PATH>", text)
    return text[:4000]


class PairingTokenService:
    """Token interno persistente usado por el desktop para diagnóstico local."""

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


@dataclass(slots=True, frozen=True)
class EphemeralCredential:
    token: str
    expires_at: int


class EphemeralCredentialService:
    """Lee/escribe la credencial corta compartida con el bridge Native Messaging."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def issue(self, ttl_seconds: int = MAX_EPHEMERAL_TTL_SECONDS, now: int | None = None) -> EphemeralCredential:
        current = int(time.time()) if now is None else int(now)
        ttl = max(1, min(int(ttl_seconds), MAX_EPHEMERAL_TTL_SECONDS))
        credential = EphemeralCredential(
            token=secrets.token_urlsafe(36),
            expires_at=current + ttl,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "token": credential.token,
                    "expiresAt": credential.expires_at,
                },
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        try:
            os.chmod(temp, 0o600)
        except OSError:
            pass
        temp.replace(self.path)
        return credential

    def current(self) -> EphemeralCredential | None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            token = str(payload["token"])
            expires_at = int(payload["expiresAt"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        if len(token) < 32:
            return None
        return EphemeralCredential(token=token, expires_at=expires_at)

    def is_valid(self, candidate: str, now: int | None = None) -> bool:
        credential = self.current()
        if credential is None:
            return False
        current = int(time.time()) if now is None else int(now)
        if current > credential.expires_at:
            return False
        if not candidate or len(candidate) != len(credential.token):
            return False
        return secrets.compare_digest(candidate, credential.token)
