"""Supresión textual temporal del eco generado por TTS local.

La captura de audio continúa activa. Esta capa solo ignora hipótesis que coinciden
claramente con texto que MilyVoice acaba de sintetizar, evitando perder al
interlocutor mientras suena la traducción española.
"""

from __future__ import annotations

import re
import time
import unicodedata
from collections import deque
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True, slots=True)
class _RecentTts:
    text: str
    expires_at: float


class EchoGuard:
    def __init__(self, *, ttl_seconds: float = 6.0, max_entries: int = 8) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds debe ser positivo")
        self.ttl_seconds = float(ttl_seconds)
        self._items: deque[_RecentTts] = deque(maxlen=max(1, int(max_entries)))

    @staticmethod
    def normalize(text: str) -> str:
        decomposed = unicodedata.normalize("NFKD", text or "")
        without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
        lowered = without_marks.casefold()
        return " ".join(re.findall(r"[\w]+", lowered, flags=re.UNICODE))

    def _prune(self, now: float) -> None:
        while self._items and self._items[0].expires_at < now:
            self._items.popleft()

    def register(self, text: str, *, now: float | None = None) -> None:
        normalized = self.normalize(text)
        if not normalized:
            return
        current = time.monotonic() if now is None else float(now)
        self._prune(current)
        self._items.append(_RecentTts(normalized, current + self.ttl_seconds))

    @staticmethod
    def _similar(left: str, right: str) -> bool:
        if not left or not right:
            return False
        if left == right:
            return True
        left_tokens = set(left.split())
        right_tokens = set(right.split())
        if left_tokens and right_tokens:
            overlap = len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))
            if overlap >= 0.9 and min(len(left), len(right)) >= 5:
                return True
        return SequenceMatcher(None, left, right).ratio() >= 0.84

    def matches(self, text: str, *, now: float | None = None) -> bool:
        candidate = self.normalize(text)
        if not candidate:
            return False
        current = time.monotonic() if now is None else float(now)
        self._prune(current)
        return any(self._similar(candidate, item.text) for item in self._items)
