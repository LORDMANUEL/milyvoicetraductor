"""Estabilización ligera de hipótesis ASR para streaming.

Whisper puede reescribir las últimas palabras cuando recibe más audio. Esta clase
expone inmediatamente la hipótesis completa para UI, pero solo marca como estable
un prefijo que ya tiene suficiente contexto semántico. Así evitamos mandar a MT
fragmentos como ``I don't think we should`` que son rápidos de reconocer pero
inestables o ambiguos al traducirse aisladamente.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Han se tokeniza carácter por carácter para que el prefijo incremental chino no
# parezca una única palabra distinta en cada decode. La alternativa Han va primero.
_WORD_RE = re.compile(r"[\u4e00-\u9fff]|[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
_DANGLING_ENGLISH = {
    "a",
    "an",
    "and",
    "are",
    "because",
    "but",
    "can",
    "can't",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "i",
    "if",
    "in",
    "is",
    "it",
    "not",
    "of",
    "or",
    "she",
    "should",
    "that",
    "the",
    "they",
    "this",
    "to",
    "we",
    "when",
    "will",
    "with",
    "would",
    "you",
}


@dataclass(frozen=True, slots=True)
class HypothesisState:
    partial: str
    stable: str
    stable_advanced: bool


def _normalize_text(text: str) -> str:
    return " ".join(str(text).split())


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def _is_han_unit(value: str) -> bool:
    return len(value) == 1 and "\u4e00" <= value <= "\u9fff"


def _contains_han_units(words: list[str]) -> bool:
    return any(_is_han_unit(word) for word in words)


def _join_units(words: list[str]) -> str:
    if _contains_han_units(words):
        # Para mandarín mantenemos escritura continua; números/latín dentro del
        # prefijo siguen siendo legibles y no introducimos espacios artificiales.
        return "".join(words)
    return " ".join(words)


def _prefix_ready(words: list[str]) -> bool:
    """Evita disparar MT con prefijos ingleses demasiado cortos o colgantes."""

    if not words:
        return False
    if _contains_han_units(words):
        return len(words) >= 2
    if len(words) < 3:
        return False
    last = words[-1].casefold()
    return last not in _DANGLING_ENGLISH and not last.endswith("n't")


class HypothesisStabilizer:
    """Bloquea únicamente prefijos repetidos que ya son útiles para traducción."""

    def __init__(self) -> None:
        self._previous_words: list[str] = []
        self._stable_words: list[str] = []
        self._previous_text = ""

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
            candidate = current_words[:common]
            if _prefix_ready(candidate):
                self._stable_words = candidate

        self._previous_words = current_words
        self._previous_text = partial
        return HypothesisState(
            partial=partial,
            stable=_join_units(self._stable_words),
            stable_advanced=len(self._stable_words) > previous_stable_len,
        )

    def finalize(self, text: str) -> str:
        # Un corte de silencio muy corto puede hacer que el último decode no emita
        # nada; en ese caso conservamos la última hipótesis visible en vez de perder
        # la utterance al cerrar la sesión.
        final = _normalize_text(text) or self._previous_text
        self.reset()
        return final

    def reset(self) -> None:
        self._previous_words.clear()
        self._stable_words.clear()
        self._previous_text = ""
