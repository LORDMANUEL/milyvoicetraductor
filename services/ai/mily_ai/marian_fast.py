"""Optimización segura para Marian EN→ES en streaming.

Reutiliza la traducción de un prefijo estable cuando el ASR final solo añade un
punto final. No colapsa preguntas ni exclamaciones y nunca evita las guardas de
calidad/fidelidad del traductor Marian base.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from .cpu_budget import CpuBudget
from .marian_realtime import CTranslate2RealtimeMarianTranslator


class CTranslate2FastRealtimeMarianTranslator(CTranslate2RealtimeMarianTranslator):
    """Marian realtime con caché acotada partial→final para puntuación segura."""

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget: CpuBudget | None = None,
        *,
        source_language: str = "en",
        target_language: str = "es",
        punctuation_cache_entries: int = 192,
    ):
        super().__init__(
            model_path,
            compute_profile,
            cpu_budget=cpu_budget,
            source_language=source_language,
            target_language=target_language,
        )
        if punctuation_cache_entries <= 0:
            raise ValueError("punctuation_cache_entries debe ser positivo")
        self._punctuation_cache_entries = punctuation_cache_entries
        self._periodless_cache: OrderedDict[tuple[str, str], str] = OrderedDict()

    @staticmethod
    def _normalize_stream_text(text: str) -> str:
        return " ".join(str(text).split())

    @staticmethod
    def _safe_period_reuse(value: str) -> str | None:
        cleaned = str(value).rstrip()
        if not cleaned:
            return None
        # Si Marian infirió por sí mismo pregunta/exclamación en el parcial,
        # el punto final del ASR puede cambiar la intención. En ese caso se
        # fuerza una inferencia nueva en vez de reutilizar una salida ambigua.
        if cleaned.endswith(("?", "!", "？", "！")):
            return None
        if cleaned.endswith((".", "。")):
            return cleaned
        return cleaned + "."

    def _remember_periodless(self, language: str, source: str, translated: str) -> None:
        key = (language, source)
        if key in self._periodless_cache:
            self._periodless_cache.pop(key)
        self._periodless_cache[key] = translated
        while len(self._periodless_cache) > self._punctuation_cache_entries:
            self._periodless_cache.popitem(last=False)

    def translate(self, text: str, source_language: str) -> str:
        normalized = self._normalize_stream_text(text)
        if not normalized:
            return ""

        # Únicamente se reutiliza partial→final cuando el cambio es exactamente
        # un punto y la salida parcial no contiene una intención interrogativa
        # o exclamativa propia. '?' y '!' en la fuente siempre recorren Marian.
        if normalized.endswith("."):
            periodless = normalized[:-1].rstrip()
            key = (source_language, periodless)
            cached = self._periodless_cache.get(key)
            if cached is not None:
                reused = self._safe_period_reuse(cached)
                if reused is not None:
                    self._periodless_cache.move_to_end(key)
                    return reused

        translated = super().translate(normalized, source_language)
        if not normalized.endswith((".", "?", "!", "。", "？", "！")):
            self._remember_periodless(source_language, normalized, translated)
        return translated

    def unload(self) -> None:
        self._periodless_cache.clear()
        super().unload()
