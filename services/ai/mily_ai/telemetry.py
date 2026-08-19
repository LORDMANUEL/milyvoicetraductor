"""Métricas locales y control de presión para el pipeline realtime."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Callable

from .process_memory import process_tree_memory_snapshot_mb
from .resource_governor import ResourceLimits


@dataclass(frozen=True, slots=True)
class TelemetrySnapshot:
    asr_p50_ms: float
    asr_p95_ms: float
    translation_p50_ms: float
    translation_p95_ms: float
    real_time_factor: float
    audio_queue_ms: int
    translation_queue_depth: int


class RealtimeTelemetry:
    """Ventana pequeña de métricas que nunca sale del equipo."""

    def __init__(self, max_samples: int = 64) -> None:
        if max_samples <= 0:
            raise ValueError("max_samples debe ser positivo")
        self._asr_ms: deque[float] = deque(maxlen=max_samples)
        self._translation_ms: deque[float] = deque(maxlen=max_samples)
        self._rtf: deque[float] = deque(maxlen=max_samples)
        self._lock = Lock()

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = round((len(ordered) - 1) * percentile)
        return float(ordered[max(0, min(index, len(ordered) - 1))])

    def record_asr(self, elapsed_ms: float, *, audio_ms: float) -> None:
        elapsed = max(0.0, float(elapsed_ms))
        duration = max(1.0, float(audio_ms))
        with self._lock:
            self._asr_ms.append(elapsed)
            self._rtf.append(elapsed / duration)

    def record_translation(self, elapsed_ms: float) -> None:
        with self._lock:
            self._translation_ms.append(max(0.0, float(elapsed_ms)))

    def snapshot(
        self, *, audio_queue_ms: int, translation_queue_depth: int
    ) -> TelemetrySnapshot:
        with self._lock:
            asr = list(self._asr_ms)
            translation = list(self._translation_ms)
            rtf = list(self._rtf)
        return TelemetrySnapshot(
            asr_p50_ms=self._percentile(asr, 0.50),
            asr_p95_ms=self._percentile(asr, 0.95),
            translation_p50_ms=self._percentile(translation, 0.50),
            translation_p95_ms=self._percentile(translation, 0.95),
            real_time_factor=self._percentile(rtf, 0.50),
            audio_queue_ms=max(0, int(audio_queue_ms)),
            translation_queue_depth=max(0, int(translation_queue_depth)),
        )


class LatencyController:
    """Degrada trabajo opcional antes de agotar 2 GiB o acumular frases.

    Estados:
    - ``healthy``: experiencia completa.
    - ``pressure``: conserva parciales ASR, pero omite MT parcial y diarización.
    - ``catch_up``: solo trabajo esencial/final para vaciar colas.
    - ``rescue``: subtítulos finales, sin TTS ni funciones costosas.

    Si el servidor no proporciona memoria explícita, el controlador mide el
    árbol del motor (incluidos sidecars) y suma la reserva Desktop/bridge. La
    muestra se reutiliza durante 500 ms para no recorrer procesos por cada chunk.
    """

    SOFT_MEMORY_MB = 1200.0
    CATCH_UP_MEMORY_MB = 1600.0
    RESCUE_MEMORY_MB = 1920.0

    def __init__(
        self,
        *,
        memory_provider: Callable[[], float] | None = None,
        product_reserve_mb: float | None = None,
        memory_sample_interval_seconds: float = 0.5,
    ) -> None:
        interval = float(memory_sample_interval_seconds)
        if interval <= 0:
            raise ValueError("memory_sample_interval_seconds debe ser positivo")
        limits = ResourceLimits()
        reserve = (
            float(limits.product_reserve_mb)
            if product_reserve_mb is None
            else float(product_reserve_mb)
        )
        if reserve < 0:
            raise ValueError("product_reserve_mb no puede ser negativo")
        self._memory_provider = memory_provider or (
            lambda: process_tree_memory_snapshot_mb().current_mb
        )
        self._product_reserve_mb = reserve
        self._memory_sample_interval_seconds = interval
        self._last_memory_sample_at = float("-inf")
        self._last_process_memory_mb = 0.0

    @property
    def last_process_memory_mb(self) -> float:
        """Última estimación del producto completo, no solo Python."""

        return self._last_process_memory_mb

    def _sample_product_memory(self) -> float:
        now = time.monotonic()
        if (
            now - self._last_memory_sample_at
            < self._memory_sample_interval_seconds
        ):
            return self._last_process_memory_mb
        try:
            engine_tree_mb = max(0.0, float(self._memory_provider()))
        except (OSError, TypeError, ValueError):
            engine_tree_mb = 0.0
        self._last_memory_sample_at = now
        self._last_process_memory_mb = engine_tree_mb + self._product_reserve_mb
        return self._last_process_memory_mb

    def classify(
        self,
        audio_queue_ms: int,
        translation_queue_depth: int,
        real_time_factor: float,
        *,
        translation_queue_age_ms: float = 0.0,
        process_memory_mb: float | None = None,
    ) -> str:
        audio = max(0, int(audio_queue_ms))
        translation = max(0, int(translation_queue_depth))
        age = max(0.0, float(translation_queue_age_ms))
        rtf = max(0.0, float(real_time_factor))
        if process_memory_mb is None:
            memory = self._sample_product_memory()
        else:
            memory = max(0.0, float(process_memory_mb))
            self._last_process_memory_mb = memory

        if (
            memory >= self.RESCUE_MEMORY_MB
            or audio >= 2400
            or translation >= 8
            or age >= 2400.0
            or rtf >= 1.80
        ):
            return "rescue"
        if (
            memory >= self.CATCH_UP_MEMORY_MB
            or audio >= 1200
            or translation >= 6
            or age >= 1200.0
            or rtf >= 1.25
        ):
            return "catch_up"
        if (
            memory >= self.SOFT_MEMORY_MB
            or audio >= 500
            or translation >= 3
            or age >= 700.0
            or rtf >= 0.85
        ):
            return "pressure"
        return "healthy"

    @staticmethod
    def allow_partial_translation(state: str) -> bool:
        return state == "healthy"

    @staticmethod
    def allow_partial_asr(state: str) -> bool:
        """Bajo presión moderada se conserva un parcial; catch-up usa finales."""

        return state in {"healthy", "pressure"}

    @staticmethod
    def allow_speaker_detection(state: str) -> bool:
        return state == "healthy"

    @staticmethod
    def allow_word_timestamps(state: str) -> bool:
        return state == "healthy"

    @staticmethod
    def allow_tts(state: str) -> bool:
        return state in {"healthy", "pressure"}
