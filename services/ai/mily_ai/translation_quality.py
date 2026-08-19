"""Guardas baratas de calidad/fidelidad para traducciones locales realtime.

No sustituye BLEU/COMET. Su misión es impedir dos fallos de alto impacto antes de
mostrar una frase: bucles patológicos del decoder y pérdida de información crítica
que puede detectarse de forma determinista (números y negaciones EN→ES).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass

_WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
_SENTENCE_RE = re.compile(r"[^.!?。！？]+[.!?。！？]?", re.UNICODE)
_NUMBER_RE = re.compile(r"(?<!\w)\d+(?:[.,]\d+)?(?!\w)")
_EN_NEGATION_RE = re.compile(
    r"\b(?:no|not|never|without|cannot|can't|won't|don't|doesn't|didn't|isn't|aren't|"
    r"wasn't|weren't|shouldn't|wouldn't|couldn't|mustn't)\b",
    re.IGNORECASE,
)
_ES_NEGATIONS = {"no", "nunca", "jamás", "sin", "tampoco", "ni"}


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


@dataclass(frozen=True, slots=True)
class SourceTargetFidelity:
    missing_numbers: tuple[str, ...]
    source_has_negation: bool
    target_has_negation: bool
    passed: bool
    reason: str

    def as_dict(self) -> dict[str, object]:
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


def _unique_in_order(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return tuple(output)


def analyze_source_target_fidelity(
    source: str,
    target: str,
    source_language: str,
    target_language: str,
) -> SourceTargetFidelity:
    """Comprueba invariantes críticas baratos antes de exponer la traducción.

    Los números se preservan para cualquier ruta basada en dígitos. La negación
    se valida de forma conservadora para EN→ES, donde perder un ``not`` cambia
    completamente el sentido de una orden o decisión.
    """

    source_numbers = _unique_in_order(_NUMBER_RE.findall(str(source or "")))
    target_numbers = set(_NUMBER_RE.findall(str(target or "")))
    missing_numbers = tuple(number for number in source_numbers if number not in target_numbers)
    if missing_numbers:
        return SourceTargetFidelity(
            missing_numbers=missing_numbers,
            source_has_negation=False,
            target_has_negation=False,
            passed=False,
            reason="NUMBER_LOST",
        )

    source_language = str(source_language or "").strip().lower()
    target_language = str(target_language or "").strip().lower()
    source_normalized = _normalize(source)
    target_tokens = set(_tokens(target))
    source_has_negation = bool(_EN_NEGATION_RE.search(source_normalized)) if source_language == "en" else False
    target_has_negation = bool(target_tokens & _ES_NEGATIONS) if target_language == "es" else False
    if source_language == "en" and target_language == "es" and source_has_negation and not target_has_negation:
        return SourceTargetFidelity(
            missing_numbers=(),
            source_has_negation=True,
            target_has_negation=False,
            passed=False,
            reason="NEGATION_LOST",
        )

    return SourceTargetFidelity(
        missing_numbers=(),
        source_has_negation=source_has_negation,
        target_has_negation=target_has_negation,
        passed=True,
        reason="OK",
    )


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
