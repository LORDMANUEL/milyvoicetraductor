"""Utilidades de audio PCM16 y buffer de ventanas con solapamiento."""

from __future__ import annotations

import base64
import struct
from collections.abc import Iterable

MAX_AUDIO_CHUNK_BYTES = 16000 * 2 * 5  # 5 segundos mono PCM16.


def decode_pcm16_base64(encoded: str) -> list[float]:
    """Convierte base64 PCM16 LE mono a floats [-1, 1] con límite de tamaño."""
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:  # binascii.Error varía entre versiones.
        raise ValueError("Audio base64 inválido") from exc
    if not raw or len(raw) % 2:
        raise ValueError("PCM16 inválido")
    if len(raw) > MAX_AUDIO_CHUNK_BYTES:
        raise ValueError("Chunk de audio demasiado grande")
    count = len(raw) // 2
    samples = struct.unpack(f"<{count}h", raw)
    return [sample / 32768.0 for sample in samples]


class PcmChunkBuffer:
    """Acumula audio hasta una ventana y conserva un pequeño contexto solapado."""

    def __init__(self, sample_rate: int = 16000, window_seconds: float = 2.4, overlap_seconds: float = 0.35):
        if sample_rate <= 0:
            raise ValueError("sample_rate debe ser positivo")
        if window_seconds <= 0:
            raise ValueError("window_seconds debe ser positivo")
        if overlap_seconds < 0 or overlap_seconds >= window_seconds:
            raise ValueError("overlap_seconds fuera de rango")
        self.sample_rate = sample_rate
        self.window_samples = max(1, round(window_seconds * sample_rate))
        self.overlap_samples = max(0, round(overlap_seconds * sample_rate))
        self._samples: list[float] = []

    @property
    def buffered_samples(self) -> int:
        return len(self._samples)

    def push_samples(self, samples: Iterable[float]) -> list[float] | None:
        self._samples.extend(float(value) for value in samples)
        if len(self._samples) < self.window_samples:
            return None
        window = self._samples[: self.window_samples]
        if self.overlap_samples:
            self._samples = window[-self.overlap_samples :] + self._samples[self.window_samples :]
        else:
            self._samples = self._samples[self.window_samples :]
        return window

    def flush(self) -> list[float] | None:
        if not self._samples:
            return None
        data = self._samples
        self._samples = []
        return data
