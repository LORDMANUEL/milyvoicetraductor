"""Guardas baratas de calidad/fidelidad para traducciones locales realtime.

No sustituye BLEU/COMET. Su misión es impedir dos fallos de alto impacto antes de
mostrar una frase: bucles patológicos del decoder y pérdida de información crítica
que puede detectarse de forma determinista (números y negaciones EN→ES).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass

_WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)
_SENTENCE_RE = re.compile(r"[^.!?。！？]+[.!?。！？]?", re.UNICODE)
_NUMBER_RE = re.compile(r"(?<!\w)\d+(?:[.,]\d+)?(?!\w)")
_CLOCK_RE = re.compile(r"(?<!\w)(\d{1,2})([:.])(\d{2})(?!\w)")
_TIME_CUE_RE = re.compile(
    r"\b(?:at|by|before|after|until|around|about|from|to|starts?|begins?|ends?|"
    r"meeting|appointment|deadline|o['’]?clock|a\.?m\.?|p\.?m\.?)\b",
    re.IGNORECASE,
)
_IDENTIFIER_PREFIX_RE = re.compile(
    r"\b(?:order|id|code|ticket|case|serial|vin|part)"
    r"(?:\s+(?:number|no\.?))?\s*(?:#\s*)?$",
    re.IGNORECASE,
)
_EN_NEGATION_RE = re.compile(
    r"\b(?:no|not|never|without|cannot|can't|won't|don't|doesn't|didn't|isn't|aren't|"
    r"wasn't|weren't|shouldn't|wouldn't|couldn't|mustn't)\b",
    re.IGNORECASE,
)
_ES_NEGATIONS = {"no", "nunca", "jamás", "sin", "tampoco", "ni"}
_TRAILING_CONNECTOR_RE = re.compile(
    r"\b(?:y|e|o|u|pero|and|or|but|then)\s*$",
    re.IGNORECASE,
)
_ES_SMALL_NUMBERS = {
    0: ("cero",),
    1: ("uno", "una"),
    2: ("dos",),
    3: ("tres",),
    4: ("cuatro",),
    5: ("cinco",),
    6: ("seis",),
    7: ("siete",),
    8: ("ocho",),
    9: ("nueve",),
    10: ("diez",),
    11: ("once",),
    12: ("doce",),
    13: ("trece",),
    14: ("catorce",),
    15: ("quince",),
    16: ("dieciseis",),
    17: ("diecisiete",),
    18: ("dieciocho",),
    19: ("diecinueve",),
    20: ("veinte",),
    21: ("veintiuno", "veintiuna"),
    22: ("veintidos",),
    23: ("veintitres",),
    24: ("veinticuatro",),
    25: ("veinticinco",),
    26: ("veintiseis",),
    27: ("veintisiete",),
    28: ("veintiocho",),
    29: ("veintinueve",),
}
_ES_TENS = {
    30: "treinta",
    40: "cuarenta",
    50: "cincuenta",
    60: "sesenta",
    70: "setenta",
    80: "ochenta",
    90: "noventa",
}


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


def _accentfold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", _normalize(value))
    return "".join(character for character in decomposed if not unicodedata.combining(character))


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


def _spanish_integer_forms(value: int) -> tuple[str, ...]:
    if value in _ES_SMALL_NUMBERS:
        return _ES_SMALL_NUMBERS[value]
    if value not in range(30, 100):
        return ()
    tens = (value // 10) * 10
    units = value % 10
    base = _ES_TENS.get(tens)
    if base is None:
        return ()
    if units == 0:
        return (base,)
    unit_forms = _ES_SMALL_NUMBERS.get(units, ())
    return tuple(f"{base} y {unit}" for unit in unit_forms)


def _target_contains_number_words(value: int, target_accentfold: str) -> bool:
    for form in _spanish_integer_forms(value):
        pattern = rf"(?<!\w){re.escape(form)}(?!\w)"
        if re.search(pattern, target_accentfold):
            return True
    return False


def _small_integer_preserved(
    raw_number: str,
    target_numbers: set[str],
    target_accentfold: str,
    *,
    allow_leading_zero: bool = False,
) -> bool:
    if raw_number in target_numbers:
        return True
    if not raw_number.isdigit():
        return False
    if len(raw_number) > 1 and raw_number.startswith("0") and not allow_leading_zero:
        return False
    value = int(raw_number)
    if not 0 <= value <= 99:
        return False
    if any(item.isdigit() and int(item) == value for item in target_numbers):
        return True
    return _target_contains_number_words(value, target_accentfold)


def _number_requires_exact(source: str, match: re.Match[str]) -> bool:
    raw = match.group(0)
    if not raw.isdigit():
        return True
    if len(raw) > 1 and raw.startswith("0"):
        return True
    if int(raw) > 99:
        return True
    prefix = str(source or "")[max(0, match.start() - 48) : match.start()]
    return bool(_IDENTIFIER_PREFIX_RE.search(prefix))


def _dot_clock_has_time_context(source: str, match: re.Match[str]) -> bool:
    if match.group(2) != ".":
        return True
    start = max(0, match.start() - 48)
    end = min(len(source), match.end() + 24)
    return bool(_TIME_CUE_RE.search(source[start:end]))


def _missing_en_es_numbers(source: str, target: str) -> tuple[str, ...]:
    """Preserva datos críticos sin confundir una hora traducida con pérdida numérica.

    IDs/códigos, números grandes, decimales y valores con ceros iniciales deben
    sobrevivir literalmente. Los enteros pequeños pueden expresarse con palabras
    españolas. Las horas aceptan ``9:00``/``9.00 → nueve`` y
    ``5:30``/``5.30 → cinco y media`` cuando un punto aparece en contexto horario.
    Un decimal ordinario como un precio 5.30 continúa exigiendo preservación exacta.
    """

    source_text = str(source or "")
    target_text = str(target or "")
    target_numbers = set(_NUMBER_RE.findall(target_text))
    target_accentfold = _accentfold(target_text)
    target_tokens = set(_tokens(target_accentfold))
    missing: list[str] = []
    covered_spans: list[tuple[int, int]] = []

    for clock in _CLOCK_RE.finditer(source_text):
        if not _dot_clock_has_time_context(source_text, clock):
            continue
        covered_spans.append(clock.span())
        hour_raw, _separator, minute_raw = clock.groups()
        hour_value = int(hour_raw)
        hour_ok = _small_integer_preserved(
            str(hour_value),
            target_numbers,
            target_accentfold,
            allow_leading_zero=True,
        )
        if not hour_ok:
            missing.append(hour_raw)

        minute_value = int(minute_raw)
        if minute_value == 0:
            continue
        minute_ok = _small_integer_preserved(
            str(minute_value),
            target_numbers,
            target_accentfold,
            allow_leading_zero=True,
        )
        if minute_value == 30:
            minute_ok = minute_ok or "media" in target_tokens
        elif minute_value == 15:
            minute_ok = minute_ok or "cuarto" in target_tokens
        if not minute_ok:
            missing.append(minute_raw)

    for match in _NUMBER_RE.finditer(source_text):
        if any(start <= match.start() and match.end() <= end for start, end in covered_spans):
            continue
        raw = match.group(0)
        if raw in target_numbers:
            continue
        if not _number_requires_exact(source_text, match) and _small_integer_preserved(
            raw,
            target_numbers,
            target_accentfold,
        ):
            continue
        missing.append(raw)

    return _unique_in_order(missing)


def analyze_source_target_fidelity(
    source: str,
    target: str,
    source_language: str,
    target_language: str,
) -> SourceTargetFidelity:
    """Comprueba invariantes críticas baratos antes de exponer la traducción.

    Para EN→ES se permiten equivalencias numéricas lingüísticamente fieles en
    cantidades pequeñas/horas, pero IDs y códigos siguen siendo exactos. En otras
    rutas los números continúan exigiéndose literalmente. La negación se valida de
    forma conservadora para EN→ES, donde perder un ``not`` cambia completamente el
    sentido de una orden o decisión.
    """

    source_language = str(source_language or "").strip().lower()
    target_language = str(target_language or "").strip().lower()
    if source_language == "en" and target_language == "es":
        missing_numbers = _missing_en_es_numbers(source, target)
    else:
        source_numbers = _unique_in_order(_NUMBER_RE.findall(str(source or "")))
        target_numbers = set(_NUMBER_RE.findall(str(target or "")))
        missing_numbers = tuple(
            number for number in source_numbers if number not in target_numbers
        )
    if missing_numbers:
        return SourceTargetFidelity(
            missing_numbers=missing_numbers,
            source_has_negation=False,
            target_has_negation=False,
            passed=False,
            reason="NUMBER_LOST",
        )

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


def non_repetitive_ngram_prefix(text: str, *, ngram_size: int = 3) -> str:
    """Recupera el prefijo anterior a un bucle dentro de una sola oración.

    Solo debe usarse después de que ``analyze_translation_quality`` haya rechazado
    la salida completa. Se buscan límites donde reaparece un n-grama y se conserva
    el prefijo más largo que vuelve a pasar la misma guarda. La fidelidad semántica
    (números/negaciones) se valida después por el llamador.
    """

    if ngram_size < 2:
        raise ValueError("ngram_size debe ser al menos 2")
    raw = str(text or "").strip()
    if not raw:
        return ""

    matches = list(_WORD_RE.finditer(raw))
    if len(matches) < ngram_size * 2:
        return ""

    normalized_tokens = [match.group(0).casefold() for match in matches]
    seen: set[tuple[str, ...]] = set()
    repeated_offsets: list[int] = []
    for index in range(len(normalized_tokens) - ngram_size + 1):
        ngram = tuple(normalized_tokens[index : index + ngram_size])
        if ngram in seen:
            repeated_offsets.append(matches[index].start())
        else:
            seen.add(ngram)

    for offset in sorted(set(repeated_offsets), reverse=True):
        prefix = raw[:offset].rstrip()
        prefix = re.sub(r"[\s,;:–—-]+$", "", prefix)
        prefix = _TRAILING_CONNECTOR_RE.sub("", prefix).strip()
        if not prefix:
            continue
        if prefix[-1] not in ".!?。！？":
            prefix += "."
        if analyze_translation_quality(prefix, ngram_size=ngram_size).passed:
            return prefix
    return ""
