"""Sherpa-ONNX streaming para BetaAlpha con audio incremental y CPU mínima.

El pipeline de MilyVoice entrega ventanas acumulativas durante una utterance. Este
adaptador conserva el recognizer/stream nativos y envía únicamente las muestras
nuevas. Para packs sherpa antiguos sin ``sherpaMode`` conserva compatibilidad
mediante el adapter offline existente.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from .cpu_budget import CpuBudget, detect_cpu_budget
from .optional_providers import (
    OptionalProviderRuntimeError,
    SherpaOnnxAsr as LegacySherpaOnnxAsr,
)
from .providers import AsrSegment


class SherpaStreamingAsr(LegacySherpaOnnxAsr):
    """Online Zipformer/Paraformer residente, optimizado para CPU débil."""

    _PREFIX_SAMPLES = 256
    _FINAL_TAIL_SECONDS = 0.5

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget: CpuBudget | None = None,
        word_timestamps: bool = False,
        *,
        component: dict[str, Any] | None = None,
    ):
        super().__init__(
            model_path,
            compute_profile,
            cpu_budget=cpu_budget,
            word_timestamps=word_timestamps,
        )
        self.component = dict(component or {})
        self._online_recognizer: Any | None = None
        self._online_stream: Any | None = None
        self._stream_samples = 0
        self._utterance_prefix: tuple[float, ...] = ()
        self._last_text = ""
        self.selected_device = "cpu"
        self.fallback_used = compute_profile not in {"auto", "cpu"}
        self.fallback_reason = (
            "Los packs Sherpa BetaAlpha se certifican primero en CPU."
            if self.fallback_used
            else ""
        )

    @property
    def _mode(self) -> str:
        return str(self.component.get("sherpaMode", "")).strip().lower()

    @property
    def _is_online(self) -> bool:
        return self._mode in {"online-transducer", "online-paraformer"}

    def _component_path(self, key: str) -> str:
        value = str(self.component.get(key, "")).strip()
        if not value:
            raise OptionalProviderRuntimeError(
                "SHERPA_CONFIG_INVALID",
                f"El pack sherpa no declara {key}.",
            )
        return self._path(value)

    def _thread_count(self) -> int:
        declared = int(
            self.component.get("maxThreads", self.cpu_budget.asr_threads) or 1
        )
        return max(1, min(int(self.cpu_budget.asr_threads), declared))

    def _sample_rate(self) -> int:
        return int(self.component.get("sampleRate", 16000))

    def _load_online(self):
        if self._online_recognizer is not None:
            return self._online_recognizer
        try:
            import sherpa_onnx
        except ImportError as exc:
            raise OptionalProviderRuntimeError(
                "SHERPA_RUNTIME_MISSING",
                "sherpa-onnx no está instalado en el runtime BetaAlpha.",
            ) from exc

        common = {
            "tokens": self._component_path("tokens"),
            "num_threads": self._thread_count(),
            "sample_rate": self._sample_rate(),
            "feature_dim": int(self.component.get("featureDim", 80)),
            "decoding_method": "greedy_search",
            "enable_endpoint_detection": False,
            "provider": "cpu",
            "debug": False,
        }
        try:
            if self._mode == "online-transducer":
                self._online_recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
                    encoder=self._component_path("encoder"),
                    decoder=self._component_path("decoder"),
                    joiner=self._component_path("joiner"),
                    max_active_paths=1,
                    **common,
                )
            elif self._mode == "online-paraformer":
                self._online_recognizer = sherpa_onnx.OnlineRecognizer.from_paraformer(
                    encoder=self._component_path("encoder"),
                    decoder=self._component_path("decoder"),
                    **common,
                )
            else:
                raise OptionalProviderRuntimeError(
                    "SHERPA_CONFIG_INVALID",
                    "El modo sherpa streaming no es válido.",
                )
        except OptionalProviderRuntimeError:
            raise
        except Exception as exc:
            self._online_recognizer = None
            raise OptionalProviderRuntimeError(
                "SHERPA_MODEL_LOAD",
                "sherpa-onnx no pudo abrir el modelo streaming seleccionado.",
            ) from exc
        return self._online_recognizer

    def _close_online_stream(self) -> None:
        self._online_stream = None
        self._stream_samples = 0
        self._utterance_prefix = ()
        self._last_text = ""

    def _starts_new_utterance(self, samples: Sequence[float]) -> bool:
        if self._online_stream is None or self._stream_samples <= 0:
            return False
        if len(samples) <= self._stream_samples:
            return True
        prefix_len = min(len(samples), len(self._utterance_prefix))
        if prefix_len <= 0:
            return False
        return (
            tuple(float(value) for value in samples[:prefix_len])
            != self._utterance_prefix[:prefix_len]
        )

    def _ensure_online_stream(self, samples: Sequence[float]):
        if self._starts_new_utterance(samples):
            self._close_online_stream()
        if self._online_stream is None:
            recognizer = self._load_online()
            try:
                self._online_stream = recognizer.create_stream()
                self._utterance_prefix = tuple(
                    float(value) for value in samples[: self._PREFIX_SAMPLES]
                )
            except Exception as exc:
                self._close_online_stream()
                raise OptionalProviderRuntimeError(
                    "SHERPA_STREAM_START",
                    "sherpa-onnx no pudo iniciar el stream realtime.",
                ) from exc
        return self._online_stream

    @staticmethod
    def _result_text(recognizer: Any, stream: Any) -> str:
        get_all = getattr(recognizer, "get_result_all", None)
        if callable(get_all):
            result = get_all(stream)
            text = str(getattr(result, "text", result) or "").strip()
            if text:
                return text
        get_result = getattr(recognizer, "get_result", None)
        if callable(get_result):
            result = get_result(stream)
            return str(getattr(result, "text", result) or "").strip()
        result = getattr(stream, "result", None)
        return str(getattr(result, "text", result) or "").strip()

    def _language(self, source_language: str, text: str) -> str:
        configured = str(self.component.get("language", "auto")).strip().lower()
        if configured in {"en", "zh"} and source_language not in {
            "auto",
            configured,
        }:
            raise OptionalProviderRuntimeError(
                "SHERPA_LANGUAGE_UNSUPPORTED",
                "El pack sherpa activo no admite el idioma solicitado.",
            )
        language = configured if configured in {"en", "zh"} else source_language
        if language == "auto":
            language = (
                "zh"
                if any("\u4e00" <= char <= "\u9fff" for char in text)
                else "en"
            )
        return language

    def _segments(
        self,
        text: str,
        source_language: str,
        audio_samples: int,
    ) -> list[AsrSegment]:
        normalized = str(text or "").strip()
        if not normalized:
            return []
        return [
            AsrSegment(
                start=0.0,
                end=audio_samples / 16000.0,
                text=normalized,
                language=self._language(source_language, normalized),
            )
        ]

    def _accept_delta(self, stream: Any, normalized: list[float]) -> None:
        delta = normalized[self._stream_samples :]
        if not delta:
            return
        try:
            stream.accept_waveform(self._sample_rate(), delta)
            self._stream_samples = len(normalized)
        except Exception as exc:
            self._close_online_stream()
            raise OptionalProviderRuntimeError(
                "SHERPA_STREAM_AUDIO",
                "sherpa-onnx no pudo recibir audio realtime.",
            ) from exc

    @staticmethod
    def _decode_ready(recognizer: Any, stream: Any) -> None:
        while recognizer.is_ready(stream):
            recognizer.decode_stream(stream)

    def _online_transcribe(
        self, samples: Sequence[float], source_language: str
    ) -> list[AsrSegment]:
        normalized = [float(value) for value in samples]
        if not normalized:
            return []
        # Valida ruta antes de cargar/usar pesos.
        self._language(source_language, "")
        stream = self._ensure_online_stream(normalized)
        recognizer = self._load_online()
        self._accept_delta(stream, normalized)
        try:
            self._decode_ready(recognizer, stream)
            text = self._result_text(recognizer, stream)
        except Exception as exc:
            self._close_online_stream()
            raise OptionalProviderRuntimeError(
                "SHERPA_STREAM_DECODE",
                "sherpa-onnx no pudo actualizar la transcripción.",
            ) from exc
        if not text:
            text = self._last_text
        else:
            self._last_text = text
        return self._segments(text, source_language, len(normalized))

    def transcribe(
        self, samples: Sequence[float], source_language: str
    ) -> list[AsrSegment]:
        if not self._is_online:
            return super().transcribe(samples, source_language)
        return self._online_transcribe(samples, source_language)

    def transcribe_final(
        self, samples: Sequence[float], source_language: str
    ) -> list[AsrSegment]:
        """Cierra una utterance online conservando las últimas sílabas.

        sherpa-onnx recomienda alimentar una corta cola de silencio y marcar
        ``input_finished`` para que el decoder procese frames pendientes. El
        padding existe solo durante el cierre y no cuenta como audio de usuario.
        """

        if not self._is_online:
            return super().transcribe(samples, source_language)
        normalized = [float(value) for value in samples]
        if not normalized:
            self._close_online_stream()
            return []
        self._language(source_language, "")
        stream = self._ensure_online_stream(normalized)
        recognizer = self._load_online()
        self._accept_delta(stream, normalized)
        try:
            tail_samples = max(1, round(self._sample_rate() * self._FINAL_TAIL_SECONDS))
            stream.accept_waveform(self._sample_rate(), [0.0] * tail_samples)
            input_finished = getattr(stream, "input_finished", None)
            if callable(input_finished):
                input_finished()
            self._decode_ready(recognizer, stream)
            text = self._result_text(recognizer, stream) or self._last_text
        except Exception as exc:
            self._close_online_stream()
            raise OptionalProviderRuntimeError(
                "SHERPA_STREAM_FINALIZE",
                "sherpa-onnx no pudo finalizar la transcripción.",
            ) from exc
        finally:
            self._close_online_stream()
        return self._segments(text, source_language, len(normalized))

    def finish_utterance(self) -> None:
        """Compatibilidad para consumidores que no requieren el texto final."""

        if not self._is_online:
            return
        stream = self._online_stream
        recognizer = self._online_recognizer
        if stream is not None and recognizer is not None:
            try:
                tail_samples = max(
                    1, round(self._sample_rate() * self._FINAL_TAIL_SECONDS)
                )
                stream.accept_waveform(self._sample_rate(), [0.0] * tail_samples)
                input_finished = getattr(stream, "input_finished", None)
                if callable(input_finished):
                    input_finished()
                self._decode_ready(recognizer, stream)
            except Exception:
                pass
        self._close_online_stream()

    def warm_up(self, _source_language: str = "auto") -> None:
        if self._is_online:
            self._load_online()
        else:
            self._load()

    def unload(self) -> None:
        self._close_online_stream()
        self._online_recognizer = None
        super().unload()
        self.selected_device = None
