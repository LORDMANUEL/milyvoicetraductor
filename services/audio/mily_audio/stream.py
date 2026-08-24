"""Sequenced, monotonic metadata for normalized float PCM ingress."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np


class AudioSourceKind(StrEnum):
    MICROPHONE = "microphone"
    SYSTEM_LOOPBACK = "systemLoopback"
    BROWSER_TAB = "browserTab"
    MEDIA_FILE = "mediaFile"


@dataclass(frozen=True, slots=True)
class AudioChunk:
    source: AudioSourceKind
    sequence_id: int
    captured_monotonic_ns: int
    sample_rate: int
    channels: int
    sample_count: int
    discontinuity: bool
    samples: np.ndarray = field(repr=False, compare=False)
    sample_format: str = "float32"


class AudioIngress:
    """Attach deterministic sequence/timing metadata to normalized PCM chunks."""

    def __init__(self, clock_ns: Callable[[], int] = time.monotonic_ns) -> None:
        self._clock_ns = clock_ns
        self._next_sequence_id = 0
        self._pending_discontinuity = False

    def accept(
        self,
        samples: Iterable[float] | np.ndarray,
        *,
        source: AudioSourceKind,
        sample_rate: int,
        channels: int,
    ) -> AudioChunk:
        if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
            raise ValueError("sample_rate debe ser un entero positivo")
        if not isinstance(channels, int) or isinstance(channels, bool) or channels <= 0:
            raise ValueError("channels debe ser un entero positivo")
        if not isinstance(source, AudioSourceKind):
            try:
                source = AudioSourceKind(source)
            except (TypeError, ValueError) as exc:
                raise ValueError("fuente de audio inválida") from exc

        normalized = np.asarray(samples, dtype=np.float32).reshape(-1).copy()
        if normalized.size == 0:
            raise ValueError("el chunk de audio no puede estar vacío")
        if not bool(np.isfinite(normalized).all()):
            raise ValueError("el chunk contiene muestras no finitas")

        sequence_id = self._next_sequence_id
        captured_monotonic_ns = int(self._clock_ns())
        discontinuity = self._pending_discontinuity

        normalized.setflags(write=False)
        chunk = AudioChunk(
            source=source,
            sequence_id=sequence_id,
            captured_monotonic_ns=captured_monotonic_ns,
            sample_rate=sample_rate,
            channels=channels,
            sample_count=int(normalized.size),
            discontinuity=discontinuity,
            samples=normalized,
        )

        self._next_sequence_id += 1
        self._pending_discontinuity = False
        return chunk

    def reset(self, *, discontinuity: bool = True) -> None:
        """Begin a new sequence only when a discontinuity is explicitly declared."""

        if not discontinuity:
            return
        self._next_sequence_id = 0
        self._pending_discontinuity = True
