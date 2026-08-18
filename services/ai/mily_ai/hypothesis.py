"""Estabilización ligera de hipótesis ASR para streaming.

Whisper puede reescribir las últimas palabras cuando recibe más audio. Esta clase
expone inmediatamente la hipótesis completa para UI, pero solo marca como estable
el prefijo que coincide entre dos decodificaciones consecutivas. Así evitamos
mandar cada fluctuación de la cola a M2M100.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_RE = re.compile(r"[\w]+(?:['’][\w]+)?", re.UNICODE)


@dataclass(frozen=True, slots=True)
class HypothesisState:
    partial: str
    stable: str
    stable_advanced: bool


def _normalize_text(text: str) -> str:
    return " ".join(str(text).split())


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


class HypothesisStabilizer:
    """Bloquea únicamente palabras repetidas en hipótesis consecutivas."""

    def __init__(self) -> None:
        self._previous_words: list[str] = []
        self._stable_words: list[str] = []

    @staticmethod
    def _common_prefix_length(left: list[str], right: list[str]) -> int:
        size = min(len(left), len(right))
        index = 0
        while index < size and left[index].casefold() == right[index].casefold():
            index += 1
        return index

    def update(self, text: str) -> HypothesisState:
        partial = _normalize_text(text)
        current_words = _words(partial)
        common = self._common_prefix_length(self._previous_words, current_words)
        previous_stable_len = len(self._stable_words)

        if common > previous_stable_len:
            self._stable_words = current_words[:common]

        self._previous_words = current_words
        return HypothesisState(
            partial=partial,
            stable=" ".join(self._stable_words),
            stable_advanced=len(self._stable_words) > previous_stable_len,
        )

    def finalize(self, text: str) -> str:
        final = _normalize_text(text)
        self.reset()
        return final

    def reset(self) -> None:
        self._previous_words.clear()
        self._stable_words.clear()
