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


class _PyAudioPatchBackend:
    """Adapta las constantes del módulo PyAudioWPatch a la instancia PyAudio."""

    def __init__(self, module) -> None:
        self._audio = module.PyAudio()
        self.paFloat32 = module.paFloat32

    def get_default_wasapi_loopback(self):
        return self._audio.get_default_wasapi_loopback()

    def get_loopback_devices(self):
        return list(self._audio.get_loopback_device_info_generator())

    def open(self, **kwargs):
        return self._audio.open(**kwargs)

    def terminate(self) -> None:
        self._audio.terminate()


class WasapiLoopbackSource:
    """Fuente WASAPI normalizada a PCM float mono 16 kHz en bloques de 100 ms.

    Teams puede usar un dispositivo de salida distinto del predeterminado de
    Windows. Si el loopback actual permanece silencioso, se sondean los demás
    loopbacks WASAPI y se cambia únicamente cuando otro tiene señal real.
    """

    def __init__(
        self,
        *,
        backend_factory: Callable[[], object] | None = None,
        target_sample_rate: int = 16000,
        chunk_ms: int = 100,
        silent_chunks_before_probe: int = 30,
        activity_threshold: float = 0.003,
    ) -> None:
        if target_sample_rate <= 0 or chunk_ms <= 0:
            raise ValueError("Parámetros de loopback inválidos")
        if silent_chunks_before_probe <= 0 or activity_threshold <= 0:
            raise ValueError("Parámetros de failover WASAPI inválidos")
        self.target_sample_rate = target_sample_rate
        self.chunk_ms = chunk_ms
        self.silent_chunks_before_probe = silent_chunks_before_probe
        self.activity_threshold = float(activity_threshold)
        self._backend_factory = backend_factory or self._default_backend_factory
        self._backend = None
        self._stream = None
        self._device: LoopbackDeviceInfo | None = None
        self._input_frames = 0
        self._loopback_devices: list[dict] = []
        self._silent_chunks = 0

    @staticmethod
    def _default_backend_factory():
        try:
            import pyaudiowpatch as pyaudio
        except ImportError as exc:
            raise LoopbackError(
                "LOOPBACK_UNAVAILABLE",
                "El componente de audio WASAPI no está instalado.",
            ) from exc
        return _PyAudioPatchBackend(pyaudio)

    @property
    def device(self) -> LoopbackDeviceInfo | None:
        return self._device

    @staticmethod
    def _normalize_device(raw: dict) -> LoopbackDeviceInfo:
        channels = max(1, int(raw.get("maxInputChannels") or 0))
        rate = max(1, int(round(float(raw.get("defaultSampleRate") or 0))))
        index = int(raw["index"])
        name = str(raw.get("name") or "Audio del sistema")
        return LoopbackDeviceInfo(index, name, channels, rate)

    def _open_device(self, backend, raw: dict):
        info = self._normalize_device(raw)
        frames = max(1, round(info.sample_rate * self.chunk_ms / 1000))
        stream = backend.open(
            format=backend.paFloat32,
            channels=info.channels,
            rate=info.sample_rate,
            input=True,
            input_device_index=info.index,
            frames_per_buffer=frames,
        )
        return stream, info, frames

    def open_default(self) -> LoopbackDeviceInfo:
        if self._stream is not None and self._device is not None:
            return self._device
        backend = None
        try:
            backend = self._backend_factory()
            raw = backend.get_default_wasapi_loopback()
            candidates = (
                list(backend.get_loopback_devices())
                if hasattr(backend, "get_loopback_devices")
                else [raw]
            )
            by_index: dict[int, dict] = {int(raw["index"]): raw}
            for candidate in candidates:
                try:
                    by_index[int(candidate["index"])] = candidate
                except (KeyError, TypeError, ValueError):
                    continue
            stream, info, frames = self._open_device(backend, raw)
        except LoopbackError:
            raise
        except Exception as exc:
            if backend is not None:
                try:
                    backend.terminate()
                except Exception:
                    pass
            raise LoopbackError(
                "LOOPBACK_DEVICE",
                "Windows no pudo abrir el dispositivo de audio loopback predeterminado.",
            ) from exc

        self._backend = backend
        self._stream = stream
        self._input_frames = frames
        self._device = info
        self._loopback_devices = list(by_index.values())
        self._silent_chunks = 0
        return info

    @staticmethod
    def _resample_mono(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
        if samples.size == 0 or source_rate == target_rate:
            return samples.astype(np.float32, copy=False)
        target_length = max(1, round(samples.size * target_rate / source_rate))
        source_positions = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
        target_positions = np.linspace(0.0, 1.0, num=target_length, endpoint=False)
        return np.interp(target_positions, source_positions, samples).astype(np.float32)

    def _decode_chunk(self, raw: bytes, info: LoopbackDeviceInfo) -> np.ndarray:
        samples = np.frombuffer(raw, dtype=np.float32)
        if info.channels > 1:
            usable = samples[: samples.size - (samples.size % info.channels)]
            samples = usable.reshape(-1, info.channels).mean(axis=1)
        return self._resample_mono(samples, info.sample_rate, self.target_sample_rate)

    @staticmethod
    def _rms(samples: np.ndarray) -> float:
        if samples.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))

    @staticmethod
    def _close_stream(stream) -> None:
        try:
            stream.stop_stream()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass

    def _probe_active_alternative(self) -> np.ndarray | None:
        backend = self._backend
        current = self._device
        if backend is None or current is None:
            return None

        best: tuple[float, dict, np.ndarray] | None = None
        for raw in self._loopback_devices:
            try:
                if int(raw["index"]) == current.index:
                    continue
                probe_stream, info, frames = self._open_device(backend, raw)
                try:
                    payload = probe_stream.read(frames, exception_on_overflow=False)
                finally:
                    self._close_stream(probe_stream)
                samples = self._decode_chunk(payload, info)
                level = self._rms(samples)
                if level < self.activity_threshold:
                    continue
                if best is None or level > best[0]:
                    best = (level, raw, samples)
            except Exception:
                # Un dispositivo no utilizable no debe tumbar la captura válida actual.
                continue

        if best is None:
            return None

        _, raw, samples = best
        new_stream, info, frames = self._open_device(backend, raw)
        old_stream = self._stream
        self._stream = new_stream
        self._device = info
        self._input_frames = frames
        if old_stream is not None:
            self._close_stream(old_stream)
        return samples

    def read_chunk(self) -> list[float]:
        if self._stream is None or self._device is None:
            raise LoopbackError("LOOPBACK_DEVICE", "El audio del sistema no está iniciado.")
        try:
            raw = self._stream.read(self._input_frames, exception_on_overflow=False)
            samples = self._decode_chunk(raw, self._device)
            if self._rms(samples) >= self.activity_threshold:
                self._silent_chunks = 0
                return samples.tolist()

            self._silent_chunks += 1
            if (
                self._silent_chunks >= self.silent_chunks_before_probe
                and len(self._loopback_devices) > 1
            ):
                self._silent_chunks = 0
                alternative = self._probe_active_alternative()
                if alternative is not None:
                    return alternative.tolist()
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
        self._loopback_devices = []
        self._silent_chunks = 0
        if stream is not None:
            self._close_stream(stream)
        if backend is not None:
            try:
                backend.terminate()
            except Exception:
                pass
