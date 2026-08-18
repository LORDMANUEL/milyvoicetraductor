"""Segmentación incremental de audio para conversación en tiempo real.

Esta capa es deliberadamente barata: calcula energía/RMS antes de invocar modelos,
acumula únicamente una utterance activa y decide cuándo solicitar una inferencia
parcial o final. Silero VAD dentro de Faster-Whisper sigue siendo la segunda
línea de defensa contra ruido y falsos positivos.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Sequence


@dataclass(frozen=True, slots=True)
class AudioLevel:
    """Estado local de señal usado por UI y diagnóstico."""

    rms: float
    peak: float
    silent_ms: int
    speech: bool


@dataclass(frozen=True, slots=True)
class StreamingEvent:
    """Ventana que debe revisar el ASR, con posición absoluta en la sesión."""

    kind: Literal["partial", "final"]
    samples: list[float]
    start_sample: int
    end_sample: int


class AdaptiveSpeechSegmenter:
    """Energy gate + ventanas adaptativas para conversación.

    No intenta reemplazar a un VAD neuronal. Su propósito es evitar llamadas
    obvias a Whisper durante silencio y reducir la espera inicial del antiguo
    buffer fijo de dos segundos.
    """

    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        first_decode_ms: int = 900,
        partial_step_ms: int = 450,
        finalize_silence_ms: int = 250,
        max_utterance_ms: int = 2400,
        energy_threshold: float = 0.012,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError("sample_rate debe ser positivo")
        if not 0 < first_decode_ms < max_utterance_ms:
            raise ValueError("first_decode_ms fuera de rango")
        if not 0 < partial_step_ms < max_utterance_ms:
            raise ValueError("partial_step_ms fuera de rango")
        if finalize_silence_ms <= 0:
            raise ValueError("finalize_silence_ms debe ser positivo")
        if max_utterance_ms <= first_decode_ms:
            raise ValueError("max_utterance_ms debe superar first_decode_ms")
        if energy_threshold <= 0:
            raise ValueError("energy_threshold debe ser positivo")

        self.sample_rate = sample_rate
        self.first_decode_samples = self._ms_to_samples(first_decode_ms)
        self.partial_step_samples = self._ms_to_samples(partial_step_ms)
        self.finalize_silence_samples = self._ms_to_samples(finalize_silence_ms)
        self.max_utterance_samples = self._ms_to_samples(max_utterance_ms)
        self.energy_threshold = float(energy_threshold)

        self._buffer: list[float] = []
        self._trailing_silence_samples = 0
        self._last_partial_samples = 0
        self._silent_ms = 0
        self._speech_active = False
        self._absolute_samples = 0
        self._utterance_start_sample = 0
        self._level = AudioLevel(rms=0.0, peak=0.0, silent_ms=0, speech=False)

    def _ms_to_samples(self, milliseconds: int) -> int:
        return max(1, round(milliseconds * self.sample_rate / 1000))

    @property
    def speech_active(self) -> bool:
        return self._speech_active

    @property
    def buffered_samples(self) -> int:
        return len(self._buffer)

    @property
    def level(self) -> AudioLevel:
        return self._level

    @staticmethod
    def _energy(samples: Sequence[float]) -> tuple[float, float]:
        if not samples:
            return 0.0, 0.0
        peak = max(abs(float(value)) for value in samples)
        square_sum = sum(float(value) * float(value) for value in samples)
        return math.sqrt(square_sum / len(samples)), peak

    def push(self, samples: Sequence[float]) -> list[StreamingEvent]:
        if not samples:
            return []

        normalized = [float(value) for value in samples]
        chunk_start = self._absolute_samples
        self._absolute_samples += len(normalized)
        rms, peak = self._energy(normalized)
        voiced = rms >= self.energy_threshold
        chunk_ms = round(len(normalized) * 1000 / self.sample_rate)

        if voiced:
            self._silent_ms = 0
        else:
            self._silent_ms += chunk_ms

        self._level = AudioLevel(
            rms=rms,
            peak=peak,
            silent_ms=self._silent_ms,
            speech=voiced,
        )

        # Silencio fuera de una utterance activa no consume memoria ni ASR.
        if not self._speech_active and not voiced:
            return []

        if not self._speech_active:
            self._speech_active = True
            self._utterance_start_sample = chunk_start
            self._buffer.clear()
            self._trailing_silence_samples = 0
            self._last_partial_samples = 0

        self._buffer.extend(normalized)
        if voiced:
            self._trailing_silence_samples = 0
        else:
            self._trailing_silence_samples += len(normalized)

        events: list[StreamingEvent] = []
        current = len(self._buffer)

        if current >= self.first_decode_samples:
            enough_since_last = (
                self._last_partial_samples == 0
                or current - self._last_partial_samples >= self.partial_step_samples
            )
            if enough_since_last and current < self.max_utterance_samples:
                events.append(
                    StreamingEvent(
                        "partial",
                        self._buffer.copy(),
                        self._utterance_start_sample,
                        self._utterance_start_sample + current,
                    )
                )
                self._last_partial_samples = current

        final_by_silence = (
            self._trailing_silence_samples >= self.finalize_silence_samples
            and current >= self.first_decode_samples
        )
        final_by_cap = current >= self.max_utterance_samples
        if final_by_silence or final_by_cap:
            final_samples = self._buffer[: self.max_utterance_samples]
            events.append(
                StreamingEvent(
                    "final",
                    final_samples,
                    self._utterance_start_sample,
                    self._utterance_start_sample + len(final_samples),
                )
            )
            self._reset_utterance()

        return events

    def flush(self) -> list[StreamingEvent]:
        """Finaliza audio pendiente al detener la sesión."""

        if not self._buffer:
            return []
        samples = self._buffer.copy()
        event = StreamingEvent(
            "final",
            samples,
            self._utterance_start_sample,
            self._utterance_start_sample + len(samples),
        )
        self._reset_utterance()
        return [event]

    def _reset_utterance(self) -> None:
        self._buffer.clear()
        self._trailing_silence_samples = 0
        self._last_partial_samples = 0
        self._speech_active = False
