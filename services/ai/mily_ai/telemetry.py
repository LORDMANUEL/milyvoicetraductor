"""Métricas locales y control de presión para el pipeline realtime."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock


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
    """Clasifica presión sin sacrificar trabajo final de ASR o traducción."""

    def classify(
        self, audio_queue_ms: int, translation_queue_depth: int, real_time_factor: float
    ) -> str:
        audio = max(0, int(audio_queue_ms))
        translation = max(0, int(translation_queue_depth))
        rtf = max(0.0, float(real_time_factor))
        if audio < 500 and translation <= 2 and rtf < 0.85:
            return "healthy"
        if audio < 1400 and translation <= 5 and rtf < 1.35:
            return "pressure"
        return "overloaded"

    @staticmethod
    def allow_partial_translation(state: str) -> bool:
        return state == "healthy"

    @staticmethod
    def allow_partial_asr(state: str) -> bool:
        """Los parciales son degradables; la frase final nunca pasa por este gate."""

        return state == "healthy"
