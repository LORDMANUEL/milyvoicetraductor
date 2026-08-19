"""BetaAlpha: control adaptativo de latencia, CPU y residencia de modelos.

Este módulo es deliberadamente independiente del pipeline estable: permite medir
el enfoque BetaAlpha contra Engine Hub Beta sin cambiar los contratos públicos.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


@dataclass(slots=True)
class AdaptiveStreamingController:
    fast_ms: int = 280
    normal_ms: int = 450
    slow_ms: int = 700
    pressure_ms: int = 800

    def interval_ms(self, *, rtf_p95: float, pressure: bool) -> int:
        if not math.isfinite(rtf_p95) or rtf_p95 < 0:
            raise ValueError("rtf_p95 debe ser finito y no negativo")
        if pressure:
            return self.pressure_ms
        if rtf_p95 < 0.35:
            return self.fast_ms
        if rtf_p95 <= 0.65:
            return self.normal_ms
        return self.slow_ms


@dataclass(frozen=True, slots=True)
class TranslationPlan:
    source_language: str
    full_source: str
    stable_source_prefix: str
    stable_translation_prefix: str
    text_to_translate: str


class IncrementalTranslationPlanner:
    """Evita retraducir prefijos idénticos producidos por ASR streaming."""

    def __init__(self) -> None:
        self._source = ""
        self._translation = ""
        self._language = ""

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.split())

    def plan(self, text: str, source_language: str) -> TranslationPlan:
        current = self._normalize(text)
        stable = ""
        translated = ""
        tail = current
        if self._language == source_language and self._source:
            if current == self._source:
                stable, translated, tail = self._source, self._translation, ""
            elif current.startswith(self._source + " "):
                stable = self._source
                translated = self._translation
                tail = current[len(self._source):].strip()
        return TranslationPlan(source_language, current, stable, translated, tail)

    def commit(self, plan: TranslationPlan, translated_text: str) -> None:
        translated = self._normalize(translated_text)
        if plan.stable_translation_prefix and translated:
            translated = f"{plan.stable_translation_prefix} {translated}".strip()
        elif plan.stable_translation_prefix:
            translated = plan.stable_translation_prefix
        self._source = plan.full_source
        self._translation = translated
        self._language = plan.source_language

    def reset(self) -> None:
        self._source = self._translation = self._language = ""


class VadGate:
    """VAD RMS barato antes del ASR con pre-roll para no cortar consonantes."""

    def __init__(self, *, sample_rate: int = 16000, preroll_ms: int = 160, rms_threshold: float = 0.012):
        self.sample_rate = max(8000, int(sample_rate))
        self.rms_threshold = max(0.0, float(rms_threshold))
        self._pre = deque(maxlen=max(1, int(self.sample_rate * preroll_ms / 1000)))

    @staticmethod
    def _rms(samples: Sequence[float]) -> float:
        if not samples:
            return 0.0
        return math.sqrt(sum(float(v) * float(v) for v in samples) / len(samples))

    def should_process(self, samples: Sequence[float]) -> bool:
        return self._rms(samples) >= self.rms_threshold

    def push(self, samples: Sequence[float]) -> None:
        self._pre.extend(float(v) for v in samples)

    def preroll(self) -> list[float]:
        return list(self._pre)


@dataclass(frozen=True, slots=True)
class EngineCandidate:
    engine_id: str
    latency_ms: float
    memory_mb: float
    quality: float
    stability: float

    @property
    def score(self) -> float:
        # 45% latencia, 30% memoria, 20% calidad, 5% estabilidad.
        latency = 1.0 / (1.0 + max(0.0, self.latency_ms) / 500.0)
        memory = 1.0 / (1.0 + max(0.0, self.memory_mb) / 800.0)
        quality = min(1.0, max(0.0, self.quality))
        stability = min(1.0, max(0.0, self.stability))
        return 0.45 * latency + 0.30 * memory + 0.20 * quality + 0.05 * stability


def rank_engine_candidates(candidates: Iterable[EngineCandidate]) -> list[EngineCandidate]:
    return sorted(candidates, key=lambda item: (-item.score, item.memory_mb, item.latency_ms, item.engine_id))


class EngineResidencyPolicy:
    """Un solo ASR caliente; los demás quedan instalados en disco."""

    def __init__(self) -> None:
        self.active_asr: str | None = None
        self.evicted: list[str] = []

    def activate_asr(self, engine_id: str) -> str | None:
        engine_id = str(engine_id).strip()
        if not engine_id:
            raise ValueError("engine_id requerido")
        previous = self.active_asr
        if previous and previous != engine_id:
            self.evicted.append(previous)
        self.active_asr = engine_id
        return previous


class ComputeTypeSelector:
    """Escoge el compute type más rápido entre los soportados y medidos."""

    SAFE_ORDER = ("int8_float32", "int8", "int16", "float32")

    def choose(self, *, supported: set[str], timings_ms: Mapping[str, float]) -> str:
        candidates: list[tuple[float, int, str]] = []
        for compute_type in supported:
            timing = timings_ms.get(compute_type)
            if timing is None or not math.isfinite(float(timing)) or float(timing) <= 0:
                continue
            order = self.SAFE_ORDER.index(compute_type) if compute_type in self.SAFE_ORDER else len(self.SAFE_ORDER)
            candidates.append((float(timing), order, compute_type))
        if not candidates:
            for fallback in self.SAFE_ORDER:
                if fallback in supported:
                    return fallback
            raise ValueError("No hay compute types compatibles")
        return min(candidates)[2]
