"""Deterministic text preparation, terminology and bounded context."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)
_SENTENCE_RE = re.compile(r".*?[.!?。！？]+|.+$", re.DOTALL)


def normalize_text(text: object) -> str:
    """Return NFKC-normalized text with deterministic single-space whitespace."""

    raw = unicodedata.normalize("NFKC", str(text or ""))
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    return _WHITESPACE_RE.sub(" ", raw).strip()


def segment_sentences(text: object) -> tuple[str, ...]:
    """Split on explicit terminal punctuation while retaining punctuation."""

    normalized = normalize_text(text)
    if not normalized:
        return ()
    return tuple(
        segment
        for match in _SENTENCE_RE.finditer(normalized)
        if (segment := match.group(0).strip())
    )


def _language(value: object, field: str) -> str:
    language = normalize_text(value).lower()
    if not language:
        raise ValueError(f"{field} no puede estar vacío")
    return language


@dataclass(frozen=True, slots=True)
class TerminologyRule:
    source: str
    target: str
    source_language: str
    target_language: str
    case_sensitive: bool = False

    def __post_init__(self) -> None:
        source = normalize_text(self.source)
        target = normalize_text(self.target)
        source_language = _language(self.source_language, "source_language")
        target_language = _language(self.target_language, "target_language")
        if not source or not target:
            raise ValueError("source y target terminológicos no pueden estar vacíos")
        if not isinstance(self.case_sensitive, bool):
            raise ValueError("case_sensitive debe ser boolean")
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "source_language", source_language)
        object.__setattr__(self, "target_language", target_language)


class TerminologyBook:
    """Validated immutable-ish terminology collection with route-aware selection."""

    def __init__(self, rules=()) -> None:
        validated: list[TerminologyRule] = []
        seen: set[tuple[str, str, str, bool]] = set()
        for rule in rules:
            if not isinstance(rule, TerminologyRule):
                raise ValueError("rules debe contener TerminologyRule")
            identity_source = rule.source if rule.case_sensitive else rule.source.casefold()
            key = (
                rule.source_language,
                rule.target_language,
                identity_source,
                rule.case_sensitive,
            )
            if key in seen:
                raise ValueError(
                    f"regla terminológica duplicada para {rule.source_language}->{rule.target_language}: {rule.source}"
                )
            seen.add(key)
            validated.append(rule)
        self._rules = tuple(validated)

    @property
    def rules(self) -> tuple[TerminologyRule, ...]:
        return self._rules

    @staticmethod
    def _present(text: str, rule: TerminologyRule) -> bool:
        source = rule.source
        haystack = text
        if not rule.case_sensitive:
            source = source.casefold()
            haystack = haystack.casefold()

        left_boundary = bool(source) and (source[0].isalnum() or source[0] == "_")
        right_boundary = bool(source) and (source[-1].isalnum() or source[-1] == "_")
        prefix = r"(?<!\w)" if left_boundary else ""
        suffix = r"(?!\w)" if right_boundary else ""
        return re.search(prefix + re.escape(source) + suffix, haystack, re.UNICODE) is not None

    def select(
        self,
        text: object,
        source_language: object,
        target_language: object,
    ) -> tuple[TerminologyRule, ...]:
        normalized = normalize_text(text)
        source = _language(source_language, "source_language")
        target = _language(target_language, "target_language")
        if not normalized:
            return ()
        return tuple(
            rule
            for rule in self._rules
            if rule.source_language == source
            and rule.target_language == target
            and self._present(normalized, rule)
        )


@dataclass(frozen=True, slots=True)
class ContextItem:
    text: str
    language: str


class ContextBuffer:
    """Bounded in-memory source context; no persistence and no implicit append."""

    def __init__(self, *, max_items: int = 4, max_chars: int = 512) -> None:
        if (
            not isinstance(max_items, int)
            or isinstance(max_items, bool)
            or max_items <= 0
        ):
            raise ValueError("max_items debe ser un entero positivo")
        if (
            not isinstance(max_chars, int)
            or isinstance(max_chars, bool)
            or max_chars <= 0
        ):
            raise ValueError("max_chars debe ser un entero positivo")
        self.max_items = max_items
        self.max_chars = max_chars
        self._items: list[ContextItem] = []

    def _total_chars(self) -> int:
        return sum(len(item.text) for item in self._items)

    def append(self, text: object, language: object) -> bool:
        normalized = normalize_text(text)
        if not normalized:
            return False
        language_code = _language(language, "language")
        if len(normalized) > self.max_chars:
            normalized = normalized[-self.max_chars :].lstrip()
            if not normalized:
                return False
        self._items.append(ContextItem(normalized, language_code))
        while len(self._items) > self.max_items or self._total_chars() > self.max_chars:
            self._items.pop(0)
        return True

    def snapshot(self) -> tuple[ContextItem, ...]:
        return tuple(self._items)

    def clear(self) -> None:
        self._items.clear()


@dataclass(frozen=True, slots=True)
class PreparedTranslationInput:
    text: str
    source_language: str
    target_language: str
    segments: tuple[str, ...]
    terminology: tuple[TerminologyRule, ...]
    context: tuple[ContextItem, ...]


def prepare_translation_input(
    text: object,
    source_language: object,
    target_language: object,
    *,
    terminology: TerminologyBook | None = None,
    context: ContextBuffer | None = None,
) -> PreparedTranslationInput:
    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("text no puede estar vacío")
    source = _language(source_language, "source_language")
    target = _language(target_language, "target_language")
    if terminology is not None and not isinstance(terminology, TerminologyBook):
        raise ValueError("terminology debe ser TerminologyBook")
    if context is not None and not isinstance(context, ContextBuffer):
        raise ValueError("context debe ser ContextBuffer")

    selected = terminology.select(normalized, source, target) if terminology else ()
    history = context.snapshot() if context else ()
    return PreparedTranslationInput(
        text=normalized,
        source_language=source,
        target_language=target,
        segments=segment_sentences(normalized),
        terminology=selected,
        context=history,
    )
