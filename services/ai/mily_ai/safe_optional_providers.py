"""Adapters opcionales seguros para el hot path realtime.

Moonshine conserva modelo y stream cargados entre hipótesis de una utterance.
whisper.cpp se comunica con un bridge stdio persistente; el `whisper-cli` que
carga el modelo por fragmento no se considera un runtime realtime válido.
"""
from __future__ import annotations

import json
import os
import queue
import struct
import subprocess
import threading
from pathlib import Path
from typing import Any, Sequence

from .cpu_budget import CpuBudget, detect_cpu_budget
from .optional_providers import MoonshineAsr, OptionalProviderRuntimeError
from .providers import AsrProvider, AsrSegment


class MoonshineResultAsr(MoonshineAsr):
    """Moonshine streaming residente compatible con `Transcript.lines`.

    Las ventanas de MilyVoice son acumulativas dentro de una utterance. Este
    adapter mantiene el modelo y el stream residentes, alimenta solo el delta
    nuevo y usa una huella corta del comienzo del audio para detectar una nueva
    frase aunque sea más larga que la anterior.
    """

    _PREFIX_SAMPLES = 256

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget: CpuBudget | None = None,
        word_timestamps: bool = False,
    ):
        super().__init__(model_path, compute_profile, cpu_budget, word_timestamps)
        self._stream: Any | None = None
        self._stream_samples = 0
        self._utterance_prefix: tuple[float, ...] = ()
        self._update_interval = 0.45

    def _config(self) -> dict[str, Any]:
        path = self.model_path / "moonshine-config.json"
        if not path.is_file():
            return {"modelArch": 2, "language": "en", "updateInterval": 0.45}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OptionalProviderRuntimeError(
                "MOONSHINE_CONFIG_INVALID",
                "La configuración del modelo Moonshine no es válida.",
            ) from exc
        if not isinstance(payload, dict):
            raise OptionalProviderRuntimeError(
                "MOONSHINE_CONFIG_INVALID",
                "La configuración del modelo Moonshine no es válida.",
            )
        return payload

    def _load(self):
        if self._transcriber is not None:
            return self._transcriber
        try:
            from moonshine_voice import Transcriber
        except ImportError as exc:
            raise OptionalProviderRuntimeError(
                "MOONSHINE_RUNTIME_MISSING",
                "Moonshine Voice no está instalado en este runtime.",
            ) from exc
        config = self._config()
        try:
            model_arch = int(config.get("modelArch", 2))
            self._update_interval = max(
                0.2, min(1.0, float(config.get("updateInterval", 0.45)))
            )
            options = {"return_audio_data": "false"}
            if self.word_timestamps:
                options["word_timestamps"] = "true"
            self._transcriber = Transcriber(
                str(self.model_path),
                model_arch,
                update_interval=self._update_interval,
                options=options,
            )
        except Exception as exc:
            raise OptionalProviderRuntimeError(
                "MOONSHINE_MODEL_LOAD",
                "Moonshine no pudo abrir el modelo seleccionado.",
            ) from exc
        return self._transcriber

    @staticmethod
    def _text_from_result(result: Any) -> str:
        if isinstance(result, str):
            return result.strip()
        text = str(getattr(result, "text", "") or "").strip()
        if text:
            return text
        lines = getattr(result, "lines", None)
        if lines is None:
            try:
                lines = list(result)
            except TypeError:
                return ""
        output: list[str] = []
        try:
            iterable = list(lines)
        except TypeError:
            iterable = [lines]
        for item in iterable:
            value = str(getattr(item, "text", item) or "").strip()
            if value:
                output.append(value)
        return " ".join(output).strip()

    def _close_stream(self) -> None:
        stream = self._stream
        self._stream = None
        self._stream_samples = 0
        self._utterance_prefix = ()
        if stream is None:
            return
        stop = getattr(stream, "stop", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                pass
        close = getattr(stream, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    def _starts_new_utterance(self, samples: Sequence[float]) -> bool:
        if self._stream is None or self._stream_samples <= 0 or not self._utterance_prefix:
            return False
        if len(samples) < self._stream_samples:
            return True
        prefix_len = min(len(samples), len(self._utterance_prefix))
        if prefix_len == 0:
            return False
        return tuple(float(value) for value in samples[:prefix_len]) != self._utterance_prefix[:prefix_len]

    def _ensure_stream(self, samples: Sequence[float]):
        if self._starts_new_utterance(samples):
            self._close_stream()
        if self._stream is None:
            transcriber = self._load()
            create_stream = getattr(transcriber, "create_stream", None)
            if not callable(create_stream):
                raise OptionalProviderRuntimeError(
                    "MOONSHINE_STREAMING_UNAVAILABLE",
                    "El runtime Moonshine instalado no ofrece streaming realtime.",
                )
            try:
                self._stream = create_stream(update_interval=self._update_interval)
                self._stream.start()
                self._utterance_prefix = tuple(
                    float(value) for value in samples[: self._PREFIX_SAMPLES]
                )
            except Exception as exc:
                self._stream = None
                self._utterance_prefix = ()
                raise OptionalProviderRuntimeError(
                    "MOONSHINE_STREAM_START",
                    "Moonshine no pudo iniciar el stream realtime.",
                ) from exc
        return self._stream

    def transcribe(
        self, samples: Sequence[float], source_language: str
    ) -> list[AsrSegment]:
        normalized = [float(value) for value in samples]
        if not normalized:
            return []
        stream = self._ensure_stream(normalized)
        delta = normalized[self._stream_samples :]
        if delta:
            try:
                stream.add_audio(delta, 16000)
            except TypeError:
                stream.add_audio(delta, sample_rate=16000)
            except Exception as exc:
                self._close_stream()
                raise OptionalProviderRuntimeError(
                    "MOONSHINE_STREAM_AUDIO",
                    "Moonshine no pudo recibir el audio realtime.",
                ) from exc
            self._stream_samples = len(normalized)
        try:
            result = stream.update_transcription()
        except Exception as exc:
            self._close_stream()
            raise OptionalProviderRuntimeError(
                "MOONSHINE_STREAM_DECODE",
                "Moonshine no pudo actualizar la transcripción realtime.",
            ) from exc
        text = self._text_from_result(result)
        if not text:
            return []
        language = "en" if source_language == "auto" else source_language
        return [
            AsrSegment(
                start=0.0,
                end=len(normalized) / 16000.0,
                text=text,
                language=language,
            )
        ]

    def finish_utterance(self) -> None:
        self._close_stream()

    def warm_up(self, _source_language: str = "en") -> None:
        self._load()

    def unload(self) -> None:
        self._close_stream()
        transcriber = self._transcriber
        self._transcriber = None
        close = getattr(transcriber, "close", None)
        if callable(close):
            close()


class WhisperCppBridgeAsr(AsrProvider):
    """Cliente de un bridge nativo que mantiene whisper.cpp residente."""

    MAX_RESPONSE_BYTES = 16 * 1024 * 1024

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget: CpuBudget | None = None,
        word_timestamps: bool = False,
        *,
        transport: Any | None = None,
        timeout_seconds: float = 20.0,
    ):
        self.model_path = Path(model_path)
        self.compute_profile = compute_profile
        self.cpu_budget = cpu_budget or detect_cpu_budget()
        self.word_timestamps = bool(word_timestamps)
        configured_backend = os.environ.get("MILY_WHISPER_CPP_BACKEND", "").strip().lower()
        backend = configured_backend or ("vulkan" if compute_profile == "gpu" else "cpu")
        self.backend = backend if backend in {"cpu", "cuda", "vulkan", "openvino"} else "cpu"
        self.selected_device = self.backend
        self.fallback_used = False
        self.fallback_reason = ""
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self._transport = transport
        self._lock = threading.Lock()

    def _bridge(self) -> Path:
        configured = os.environ.get("MILY_WHISPER_CPP_BRIDGE", "").strip()
        candidates = [
            Path(configured) if configured else None,
            self.model_path / "mily-whispercpp-bridge.exe",
            self.model_path / "mily-whispercpp-bridge",
        ]
        for candidate in candidates:
            if candidate is not None and candidate.is_file():
                return candidate
        raise OptionalProviderRuntimeError(
            "WHISPER_CPP_BRIDGE_MISSING",
            "No se encontró el bridge persistente autorizado de whisper.cpp.",
        )

    def _model(self) -> Path:
        models = sorted(self.model_path.glob("*.gguf")) + sorted(
            self.model_path.glob("ggml-*.bin")
        )
        if not models:
            raise OptionalProviderRuntimeError(
                "WHISPER_CPP_MODEL_MISSING",
                "El pack whisper.cpp no contiene un modelo cuantizado.",
            )
        return models[0]

    def _load(self):
        if self._transport is not None:
            return self._transport
        startup = subprocess.STARTUPINFO() if os.name == "nt" else None
        if startup is not None:
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            self._transport = subprocess.Popen(
                [
                    str(self._bridge()),
                    "--stdio",
                    "--model",
                    str(self._model()),
                    "--backend",
                    self.backend,
                    "--threads",
                    str(max(1, self.cpu_budget.asr_threads)),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                startupinfo=startup,
                creationflags=creationflags,
            )
        except OSError as exc:
            raise OptionalProviderRuntimeError(
                "WHISPER_CPP_BRIDGE_START",
                "No se pudo iniciar el bridge persistente de whisper.cpp.",
            ) from exc
        return self._transport

    @staticmethod
    def _read_exact(stream: Any, length: int) -> bytes:
        output = bytearray()
        while len(output) < length:
            chunk = stream.read(length - len(output))
            if not chunk:
                raise EOFError("El bridge whisper.cpp terminó inesperadamente")
            output.extend(chunk)
        return bytes(output)

    def _read_response(self, stream: Any) -> dict[str, Any]:
        results: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

        def reader() -> None:
            try:
                size = struct.unpack("<I", self._read_exact(stream, 4))[0]
                if size > self.MAX_RESPONSE_BYTES:
                    raise ValueError("Respuesta whisper.cpp demasiado grande")
                payload = json.loads(self._read_exact(stream, size).decode("utf-8"))
                results.put((True, payload))
            except BaseException as exc:
                results.put((False, exc))

        worker = threading.Thread(target=reader, name="mily-whispercpp-read", daemon=True)
        worker.start()
        try:
            ok, value = results.get(timeout=self.timeout_seconds)
        except queue.Empty as exc:
            self.unload()
            raise OptionalProviderRuntimeError(
                "WHISPER_CPP_TIMEOUT",
                "whisper.cpp excedió el límite de tiempo del fragmento.",
            ) from exc
        if not ok:
            self.unload()
            raise OptionalProviderRuntimeError(
                "WHISPER_CPP_PROTOCOL",
                "El bridge whisper.cpp devolvió una respuesta inválida.",
            ) from value
        if not isinstance(value, dict):
            raise OptionalProviderRuntimeError(
                "WHISPER_CPP_PROTOCOL",
                "El bridge whisper.cpp no devolvió un objeto JSON.",
            )
        return value

    def _request(self, samples: Sequence[float], source_language: str) -> dict[str, Any]:
        transport = self._load()
        request = getattr(transport, "request", None)
        if callable(request):
            payload = request([float(value) for value in samples], source_language)
            if not isinstance(payload, dict):
                raise OptionalProviderRuntimeError(
                    "WHISPER_CPP_PROTOCOL",
                    "El transport de whisper.cpp no devolvió un objeto JSON.",
                )
            return payload
        if transport.stdin is None or transport.stdout is None:
            raise OptionalProviderRuntimeError(
                "WHISPER_CPP_PROTOCOL",
                "El bridge whisper.cpp no tiene tuberías stdio.",
            )
        metadata = json.dumps(
            {
                "protocol": 1,
                "sampleRate": 16000,
                "language": source_language,
                "sampleCount": len(samples),
                "wordTimestamps": self.word_timestamps,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        pcm = struct.pack(f"<{len(samples)}f", *[float(value) for value in samples])
        with self._lock:
            try:
                transport.stdin.write(struct.pack("<II", len(metadata), len(pcm)))
                transport.stdin.write(metadata)
                transport.stdin.write(pcm)
                transport.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                self.unload()
                raise OptionalProviderRuntimeError(
                    "WHISPER_CPP_PROTOCOL",
                    "Se perdió la comunicación con whisper.cpp.",
                ) from exc
            return self._read_response(transport.stdout)

    def transcribe(
        self, samples: Sequence[float], source_language: str
    ) -> list[AsrSegment]:
        response = self._request(samples, source_language)
        text = str(response.get("text", "") or "").strip()
        if not text:
            return []
        language = str(response.get("language", "") or source_language or "auto")
        return [
            AsrSegment(
                start=0.0,
                end=len(samples) / 16000.0,
                text=text,
                language=language,
            )
        ]

    def warm_up(self, _source_language: str = "en") -> None:
        self._load()

    def unload(self) -> None:
        transport = self._transport
        self._transport = None
        if transport is None:
            return
        close = getattr(transport, "close", None)
        if callable(close):
            close()
            return
        terminate = getattr(transport, "terminate", None)
        if callable(terminate):
            terminate()
        wait = getattr(transport, "wait", None)
        if callable(wait):
            try:
                wait(timeout=2)
            except Exception:
                kill = getattr(transport, "kill", None)
                if callable(kill):
                    kill()
