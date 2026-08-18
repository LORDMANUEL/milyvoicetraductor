"""Captura local del audio reproducido por Windows mediante WASAPI loopback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


class LoopbackError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class LoopbackDeviceInfo:
    index: int
    name: str
    channels: int
    sample_rate: int


class WasapiLoopbackSource:
    """Fuente WASAPI normalizada a PCM float mono 16 kHz en bloques de 100 ms."""

    def __init__(
        self,
        *,
        backend_factory: Callable[[], object] | None = None,
        target_sample_rate: int = 16000,
        chunk_ms: int = 100,
    ) -> None:
        if target_sample_rate <= 0 or chunk_ms <= 0:
            raise ValueError("Parámetros de loopback inválidos")
        self.target_sample_rate = target_sample_rate
        self.chunk_ms = chunk_ms
        self._backend_factory = backend_factory or self._default_backend_factory
        self._backend = None
        self._stream = None
        self._device: LoopbackDeviceInfo | None = None
        self._input_frames = 0

    @staticmethod
    def _default_backend_factory():
        try:
            import pyaudiowpatch as pyaudio
        except ImportError as exc:
            raise LoopbackError(
                "LOOPBACK_UNAVAILABLE",
                "El componente de audio WASAPI no está instalado.",
            ) from exc
        return pyaudio.PyAudio()

    @property
    def device(self) -> LoopbackDeviceInfo | None:
        return self._device

    def open_default(self) -> LoopbackDeviceInfo:
        if self._stream is not None and self._device is not None:
            return self._device
        try:
            backend = self._backend_factory()
            raw = backend.get_default_wasapi_loopback()
            channels = max(1, int(raw.get("maxInputChannels") or 0))
            rate = max(1, int(round(float(raw.get("defaultSampleRate") or 0))))
            index = int(raw["index"])
            name = str(raw.get("name") or "Audio del sistema")
            if rate <= 0:
                raise ValueError("sample rate inválido")
            frames = max(1, round(rate * self.chunk_ms / 1000))
            stream = backend.open(
                format=backend.paFloat32,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=index,
                frames_per_buffer=frames,
            )
        except LoopbackError:
            raise
        except Exception as exc:
            self.close()
            raise LoopbackError(
                "LOOPBACK_DEVICE",
                "Windows no pudo abrir el dispositivo de audio loopback predeterminado.",
            ) from exc

        self._backend = backend
        self._stream = stream
        self._input_frames = frames
        self._device = LoopbackDeviceInfo(index, name, channels, rate)
        return self._device

    @staticmethod
    def _resample_mono(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
        if samples.size == 0 or source_rate == target_rate:
            return samples.astype(np.float32, copy=False)
        target_length = max(1, round(samples.size * target_rate / source_rate))
        source_positions = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
        target_positions = np.linspace(0.0, 1.0, num=target_length, endpoint=False)
        return np.interp(target_positions, source_positions, samples).astype(np.float32)

    def read_chunk(self) -> list[float]:
        if self._stream is None or self._device is None:
            raise LoopbackError("LOOPBACK_DEVICE", "El audio del sistema no está iniciado.")
        try:
            raw = self._stream.read(self._input_frames, exception_on_overflow=False)
            samples = np.frombuffer(raw, dtype=np.float32)
            channels = self._device.channels
            if channels > 1:
                usable = samples[: samples.size - (samples.size % channels)]
                samples = usable.reshape(-1, channels).mean(axis=1)
            samples = self._resample_mono(
                samples,
                self._device.sample_rate,
                self.target_sample_rate,
            )
            return samples.tolist()
        except LoopbackError:
            raise
        except Exception as exc:
            raise LoopbackError(
                "LOOPBACK_CAPTURE",
                "Se perdió la captura del audio reproducido por Windows.",
            ) from exc

    def close(self) -> None:
        stream, backend = self._stream, self._backend
        self._stream = None
        self._backend = None
        self._device = None
        self._input_frames = 0
        if stream is not None:
            try:
                stream.stop_stream()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass
        if backend is not None:
            try:
                backend.terminate()
            except Exception:
                pass
