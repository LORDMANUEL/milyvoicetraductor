"""PCM16 decoding and bounded analysis-window buffering for MilyVoice Audio."""

from __future__ import annotations

import base64
from collections.abc import Iterable

import numpy as np

MAX_AUDIO_CHUNK_BYTES = 16000 * 2 * 5  # 5 seconds mono PCM16 at 16 kHz.


def decode_pcm16_bytes(raw: bytes) -> np.ndarray:
    """Convert little-endian mono PCM16 to normalized float32 samples."""

    if not raw or len(raw) % 2:
        raise ValueError("PCM16 inválido")
    if len(raw) > MAX_AUDIO_CHUNK_BYTES:
        raise ValueError("Chunk de audio demasiado grande")
    pcm = np.frombuffer(raw, dtype="<i2")
    return pcm.astype(np.float32) / np.float32(32768.0)


def decode_pcm16_base64(encoded: str) -> list[float]:
    """Compatibility helper: Base64 -> PCM16 -> normalized samples."""

    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:  # binascii.Error varies across Python versions.
        raise ValueError("Audio base64 inválido") from exc
    return decode_pcm16_bytes(raw).tolist()


class PcmChunkBuffer:
    """Accumulate samples until a window is ready while retaining overlap."""

    def __init__(
        self,
        sample_rate: int = 16000,
        window_seconds: float = 2.4,
        overlap_seconds: float = 0.35,
    ) -> None:
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
            self._samples = (
                window[-self.overlap_samples :]
                + self._samples[self.window_samples :]
            )
        else:
            self._samples = self._samples[self.window_samples :]
        return window

    def flush(self) -> list[float] | None:
        if not self._samples:
            return None
        data = self._samples
        self._samples = []
        return data
