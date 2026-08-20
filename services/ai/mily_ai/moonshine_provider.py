"""Adaptador Moonshine streaming con modelo residente y audio incremental."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from .cpu_budget import CpuBudget, detect_cpu_budget
from .optional_providers import OptionalProviderRuntimeError
from .providers import AsrProvider, AsrSegment, AsrWord


class MoonshineStreamingAsr(AsrProvider):
    """Alimenta únicamente el delta nuevo de cada ventana acumulativa.

    `AdaptiveSpeechSegmenter` entrega ventanas crecientes dentro de una frase.
    Reenviar la ventana completa duplicaría audio y haría crecer el atraso. Este
    proveedor conserva el stream nativo, recuerda cuántas muestras ya consumió y
    ejecuta exactamente una actualización por ventana solicitada por MilyVoice.
    """

    _PREFIX_SAMPLES = 256
    _MANUAL_UPDATE_INTERVAL_SECONDS = 24 * 60 * 60.0

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget: CpuBudget | None = None,
        word_timestamps: bool = False,
    ):
        self.model_path = Path(model_path)
        self.compute_profile = compute_profile
        self.cpu_budget = cpu_budget or detect_cpu_budget()
        self.word_timestamps = bool(word_timestamps)
        self._transcriber: Any | None = None
        self._stream: Any | None = None
        self._stream_samples = 0
        self._utterance_prefix: tuple[float, ...] = ()
        self._configured_update_interval = 0.45
        self.selected_device: str | None = "cpu"
        self.fallback_used = compute_profile not in {"auto", "cpu"}
        self.fallback_reason = (
            "Moonshine usa CPU en esta versión."
            if self.fallback_used
            else ""
        )

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
            from moonshine_voice import ModelArch, Transcriber
        except ImportError as exc:
            raise OptionalProviderRuntimeError(
                "MOONSHINE_RUNTIME_MISSING",
                "Moonshine Voice no está instalado en este runtime.",
            ) from exc
        config = self._config()
        try:
            model_arch = ModelArch(int(config.get("modelArch", 2)))
            self._configured_update_interval = max(
                0.2, min(1.0, float(config.get("updateInterval", 0.45)))
            )
            options = {"return_audio_data": "false"}
            if self.word_timestamps:
                options["word_timestamps"] = "true"
            self._transcriber = Transcriber(
                str(self.model_path),
                model_arch,
                update_interval=self._configured_update_interval,
                options=options,
            )
        except Exception as exc:
            raise OptionalProviderRuntimeError(
                "MOONSHINE_MODEL_LOAD",
                "Moonshine no pudo abrir el modelo seleccionado.",
            ) from exc
        return self._transcriber

    def _close_stream(self) -> None:
        stream = self._stream
        self._stream = None
        self._stream_samples = 0
        self._utterance_prefix = ()
        if stream is None:
            return
        close = getattr(stream, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    def _starts_new_utterance(self, samples: Sequence[float]) -> bool:
        if self._stream is None or self._stream_samples <= 0:
            return False
        # Una ventana de la misma frase siempre crece. Igual o menor longitud es
        # una frase nueva, incluso cuando dos frases comienzan con el mismo audio.
        if len(samples) <= self._stream_samples:
            return True
        prefix_len = min(len(samples), len(self._utterance_prefix))
        if prefix_len == 0:
            return False
        return (
            tuple(float(value) for value in samples[:prefix_len])
            != self._utterance_prefix[:prefix_len]
        )

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
                # Stream.add_audio ya puede lanzar inferencia automáticamente.
                # Usamos un intervalo alto y controlamos nosotros una sola
                # actualización por ventana para impedir decodificación doble.
                self._stream = create_stream(
                    update_interval=self._MANUAL_UPDATE_INTERVAL_SECONDS
                )
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

    def _segments(
        self,
        result: Any,
        source_language: str,
        audio_seconds: float,
    ) -> list[AsrSegment]:
        language = "en" if source_language == "auto" else source_language
        lines = getattr(result, "lines", None)
        if lines is None:
            text = str(getattr(result, "text", result) or "").strip()
            return (
                [AsrSegment(0.0, audio_seconds, text, language)]
                if text
                else []
            )
        output: list[AsrSegment] = []
        for line in list(lines):
            text = str(getattr(line, "text", "") or "").strip()
            if not text:
                continue
            start = float(getattr(line, "start_time", 0.0) or 0.0)
            duration = float(getattr(line, "duration", 0.0) or 0.0)
            end = start + duration if duration > 0 else audio_seconds
            words: tuple[AsrWord, ...] = ()
            if self.word_timestamps:
                words = tuple(
                    AsrWord(
                        float(getattr(word, "start", 0.0) or 0.0),
                        float(getattr(word, "end", 0.0) or 0.0),
                        str(getattr(word, "text", "") or "").strip(),
                    )
                    for word in (getattr(line, "words", None) or ())
                    if str(getattr(word, "text", "") or "").strip()
                )
            output.append(AsrSegment(start, end, text, language, words))
        return output

    def transcribe(
        self, samples: Sequence[float], source_language: str
    ) -> list[AsrSegment]:
        normalized = [float(value) for value in samples]
        if not normalized:
            return []
        if source_language not in {"auto", "en"}:
            raise OptionalProviderRuntimeError(
                "MOONSHINE_LANGUAGE_UNSUPPORTED",
                "Este pack Moonshine está optimizado únicamente para inglés.",
            )
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
        return self._segments(
            result,
            source_language,
            len(normalized) / 16000.0,
        )

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
            try:
                close()
            except Exception:
                pass
        self.selected_device = None
