"""Contrato de idiomas prioritarios de MilyVoice.

Esta capa no modifica todavía el protocolo WebSocket ni proveedores. Existe para
que la arquitectura deje de asumir ``target=es`` y pueda integrar después los
cuatro fast paths sin mezclar esa migración con el cierre realtime actual.
"""

from __future__ import annotations

from dataclasses import dataclass

TIER1_LANGUAGES = frozenset({"es", "en", "zh"})

_LANGUAGE_ALIASES = {
    "auto": "auto",
    "en": "en",
    "en-us": "en",
    "en-gb": "en",
    "es": "es",
    "es-419": "es",
    "es-hn": "es",
    "zh": "zh",
    "zh-cn": "zh",
    "zh-hans": "zh",
    "cmn": "zh",
    "cmn-hans-cn": "zh",
}


@dataclass(frozen=True, slots=True)
class LanguageRoute:
    source: str
    target: str
    profile: str
    priority: int = 1


_TIER1_ROUTES = {
    ("en", "es"): LanguageRoute("en", "es", "en-es-realtime"),
    ("es", "en"): LanguageRoute("es", "en", "es-en-realtime"),
    ("zh", "es"): LanguageRoute("zh", "es", "zh-es-realtime"),
    ("es", "zh"): LanguageRoute("es", "zh", "es-zh-realtime"),
}


def normalize_language(value: str | None) -> str:
    normalized = (value or "").strip().lower().replace("_", "-")
    return _LANGUAGE_ALIASES.get(normalized, normalized)


def get_tier1_route(source: str | None, target: str | None) -> LanguageRoute | None:
    source_code = normalize_language(source)
    target_code = normalize_language(target)
    if "auto" in {source_code, target_code}:
        return None
    return _TIER1_ROUTES.get((source_code, target_code))


def is_tier1_route(source: str | None, target: str | None) -> bool:
    return get_tier1_route(source, target) is not None
