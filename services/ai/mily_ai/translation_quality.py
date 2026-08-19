"""Guardas baratas contra repetición patológica en traducciones locales.

No intenta evaluar semántica o sustituir métricas BLEU/COMET. Su función es
rechazar bucles obvios del decodificador antes de mostrar una frase repetida al
usuario o aprobar un modelo durante MegaBench.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass

_WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
_SENTENCE_RE = re.compile(r"[^.!?。！？]+[.!?。！？]?", re.UNICODE)


@dataclass(frozen=True, slots=True)
class TranslationQuality:
    token_count: int
    ngram_size: int
    repeated_ngram_ratio: float
    max_ngram_occurrences: int
    repeated_sentence_count: int
    passed: bool
    reason: str

    def as_dict(self) -> dict[str, int | float | bool | str]:
        return asdict(self)


def _normalize(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


def _tokens(value: str) -> list[str]:
    return _WORD_RE.findall(_normalize(value))


def _sentences(value: str) -> list[str]:
    return [
        _normalize(part.strip(" .!?。！？"))
        for part in _SENTENCE_RE.findall(str(value or ""))
        if _normalize(part.strip(" .!?。！？"))
    ]


def analyze_translation_quality(
    text: str,
    *,
    ngram_size: int = 3,
    max_repeated_ngram_ratio: float = 0.25,
    max_ngram_occurrences: int = 2,
) -> TranslationQuality:
    """Detecta bucles de n-gramas y oraciones duplicadas.

    Las frases menores de ocho tokens no se penalizan por repetición de n-gramas:
    expresiones legítimas como "muy, muy bien" no deben desaparecer. Una salida
    vacía siempre falla.
    """

    if ngram_size < 2:
        raise ValueError("ngram_size debe ser al menos 2")
    if not 0.0 <= max_repeated_ngram_ratio <= 1.0:
        raise ValueError("max_repeated_ngram_ratio fuera de rango")
    if max_ngram_occurrences < 1:
        raise ValueError("max_ngram_occurrences debe ser positivo")

    normalized = _normalize(text)
    tokens = _tokens(normalized)
    if not tokens:
        return TranslationQuality(0, ngram_size, 0.0, 0, 0, False, "EMPTY")

    ngrams = [
        tuple(tokens[index : index + ngram_size])
        for index in range(max(0, len(tokens) - ngram_size + 1))
    ]
    counts = Counter(ngrams)
    repeat_instances = sum(max(0, count - 1) for count in counts.values())
    repeated_ratio = repeat_instances / max(1, len(ngrams))
    maximum = max(counts.values(), default=1)

    sentence_counts = Counter(_sentences(normalized))
    repeated_sentences = sum(
        max(0, count - 1) for count in sentence_counts.values()
    )

    long_enough = len(tokens) >= 8
    if repeated_sentences:
        passed, reason = False, "REPEATED_SENTENCE"
    elif long_enough and maximum > max_ngram_occurrences:
        passed, reason = False, "REPEATED_NGRAM"
    elif long_enough and repeated_ratio > max_repeated_ngram_ratio:
        passed, reason = False, "REPETITION_RATIO"
    else:
        passed, reason = True, "OK"

    return TranslationQuality(
        token_count=len(tokens),
        ngram_size=ngram_size,
        repeated_ngram_ratio=round(repeated_ratio, 6),
        max_ngram_occurrences=maximum,
        repeated_sentence_count=repeated_sentences,
        passed=passed,
        reason=reason,
    )


def non_repetitive_sentence_prefix(text: str) -> str:
    """Conserva el prefijo de oraciones sano cuando aparece una cola en bucle."""

    parts = [part.strip() for part in _SENTENCE_RE.findall(str(text or "")) if part.strip()]
    accepted: list[str] = []
    for part in parts:
        candidate = " ".join([*accepted, part]).strip()
        if analyze_translation_quality(candidate).passed:
            accepted.append(part)
            continue
        break
    return " ".join(accepted).strip()
