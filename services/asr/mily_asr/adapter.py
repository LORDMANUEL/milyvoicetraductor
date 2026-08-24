"""Provider-neutral lazy adapters over the proven MilyVoice 2.x ASR providers."""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AsrAdapterError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class AsrWord:
    start_ms: float
    end_ms: float
    text: str


@dataclass(frozen=True, slots=True)
class AsrSegment:
    start_ms: float
    end_ms: float
    text: str
    language: str | None
    words: tuple[AsrWord, ...] = ()


@dataclass(frozen=True, slots=True)
class AsrMetrics:
    elapsed_ms: float
    audio_duration_ms: float
    rtf: float


@dataclass(frozen=True, slots=True)
class AsrResult:
    request_id: str
    utterance_id: str
    sequence_id: int
    media_start_ns: int
    media_end_ns: int
    engine_id: str
    source_language: str
    detected_language: str | None
    final: bool
    text: str
    segments: tuple[AsrSegment, ...]
    metrics: AsrMetrics


ProviderBuilder = Callable[[dict[str, Any], Path, str, object, bool], object]
CpuBudgetBuilder = Callable[[str, int | None], object]
Clock = Callable[[], int]


def _default_provider_builder(
    component: dict[str, Any],
    model_path: Path,
    compute_profile: str,
    cpu_budget: object,
    word_timestamps: bool,
) -> object:
    try:
        from mily_ai.provider_factory import build_asr_provider
    except ImportError as exc:
        raise AsrAdapterError(
            "ASR_LEGACY_RUNTIME_MISSING",
            "La fábrica ASR del runtime privado no está disponible.",
        ) from exc
    return build_asr_provider(
        component,
        model_path,
        compute_profile,
        cpu_budget,  # type: ignore[arg-type]
        word_timestamps,
    )


def _default_cpu_budget_builder(profile: str, physical_cores: int | None) -> object:
    try:
        from mily_ai.cpu_budget import detect_cpu_budget
    except ImportError as exc:
        raise AsrAdapterError(
            "ASR_LEGACY_RUNTIME_MISSING",
            "El presupuesto CPU del runtime privado no está disponible.",
        ) from exc
    return detect_cpu_budget(profile=profile, physical_cores=physical_cores)


class LegacyAsrAdapter:
    provider_id = ""
    engine_id = ""

    def __init__(
        self,
        *,
        provider_builder: ProviderBuilder | None = None,
        cpu_budget_builder: CpuBudgetBuilder | None = None,
        clock_ns: Clock = time.perf_counter_ns,
    ) -> None:
        self._provider_builder = provider_builder or _default_provider_builder
        self._cpu_budget_builder = cpu_budget_builder or _default_cpu_budget_builder
        self._clock_ns = clock_ns
        self._provider: object | None = None
        self._config: dict[str, object] = {}

    @staticmethod
    def _positive_int(value: object, *, optional: bool = False) -> int | None:
        if value is None and optional:
            return None
        if isinstance(value, bool):
            return None
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def load(self, config: Mapping[str, object] | None) -> None:
        if self._provider is not None:
            return
        if not isinstance(config, Mapping):
            raise AsrAdapterError("ASR_CONFIG_INVALID", "La configuración ASR debe ser un objeto.")

        model_path_value = config.get("modelPath")
        if not isinstance(model_path_value, str) or not model_path_value.strip():
            raise AsrAdapterError(
                "ASR_MODEL_PATH_REQUIRED",
                "modelPath es obligatorio para cargar el adapter ASR.",
            )

        raw_component = config.get("component", {})
        if not isinstance(raw_component, Mapping):
            raise AsrAdapterError("ASR_CONFIG_INVALID", "component debe ser un objeto.")
        component = dict(raw_component)
        declared_provider = str(component.get("provider", "") or "").strip().lower()
        if declared_provider and declared_provider != self.provider_id:
            raise AsrAdapterError(
                "ASR_PROVIDER_CONFLICT",
                f"El adapter {self.engine_id} no puede cargar provider {declared_provider}.",
            )
        component["provider"] = self.provider_id

        compute_profile = str(config.get("computeProfile", "auto") or "auto").strip().lower()
        cpu_profile = str(config.get("cpuProfile", "balanced") or "balanced").strip().lower()
        physical_raw = config.get("physicalCores")
        physical_cores = self._positive_int(physical_raw, optional=True)
        if physical_raw is not None and physical_cores is None:
            raise AsrAdapterError(
                "ASR_CONFIG_INVALID",
                "physicalCores debe ser un entero positivo.",
            )
        word_timestamps = bool(config.get("wordTimestamps", True))
        warmup_language = str(config.get("warmupLanguage", "en") or "en").strip().lower()
        if not warmup_language:
            raise AsrAdapterError("ASR_CONFIG_INVALID", "warmupLanguage no puede estar vacío.")

        budget = self._cpu_budget_builder(cpu_profile, physical_cores)
        provider = self._provider_builder(
            component,
            Path(model_path_value.strip()),
            compute_profile,
            budget,
            word_timestamps,
        )
        if provider is None:
            raise AsrAdapterError("ASR_PROVIDER_LOAD_FAILED", "La fábrica ASR devolvió un provider vacío.")

        warm_up = getattr(provider, "warm_up", None)
        if callable(warm_up):
            warm_up(warmup_language)

        self._provider = provider
        self._config = dict(config)

    def unload(self) -> None:
        provider = self._provider
        self._provider = None
        self._config = {}
        if provider is None:
            return
        unload = getattr(provider, "unload", None)
        if callable(unload):
            unload()

    def health(self) -> bool:
        return self._provider is not None

    @staticmethod
    def _request_metadata(request: object) -> tuple[str, str, bool]:
        metadata = getattr(request, "metadata", None)
        if not isinstance(metadata, Mapping):
            raise AsrAdapterError("ASR_METADATA_INVALID", "metadata ASR es obligatoria.")
        utterance_id = metadata.get("utteranceId")
        source_language = metadata.get("sourceLanguage")
        final = metadata.get("final", False)
        if not isinstance(utterance_id, str) or not utterance_id.strip():
            raise AsrAdapterError("ASR_METADATA_INVALID", "utteranceId es obligatorio.")
        if not isinstance(source_language, str) or not source_language.strip():
            raise AsrAdapterError("ASR_METADATA_INVALID", "sourceLanguage es obligatorio.")
        if not isinstance(final, bool):
            raise AsrAdapterError("ASR_METADATA_INVALID", "final debe ser boolean.")
        return utterance_id.strip(), source_language.strip().lower(), final

    @staticmethod
    def _validate_window(frame: object) -> object:
        sample_rate = getattr(frame, "sample_rate", None)
        channels = getattr(frame, "channels", None)
        sample_format = getattr(frame, "sample_format", None)
        sample_count = getattr(frame, "sample_count", None)
        sequence_id = getattr(frame, "sequence_id", None)
        media_start_ns = getattr(frame, "media_start_ns", None)
        duration_ns = getattr(frame, "duration_ns", None)
        payload = getattr(frame, "payload", None)

        scalar_valid = (
            sample_rate == 16000
            and channels == 1
            and sample_format == "float32"
            and isinstance(sample_count, int)
            and not isinstance(sample_count, bool)
            and sample_count > 0
            and isinstance(sequence_id, int)
            and not isinstance(sequence_id, bool)
            and sequence_id >= 0
            and isinstance(media_start_ns, int)
            and not isinstance(media_start_ns, bool)
            and media_start_ns >= 0
            and isinstance(duration_ns, int)
            and not isinstance(duration_ns, bool)
            and duration_ns > 0
        )
        if not scalar_valid:
            raise AsrAdapterError("ASR_WINDOW_INVALID", "La ventana ASR debe ser 16 kHz mono float32 válida.")
        try:
            payload_len = len(payload)  # type: ignore[arg-type]
        except (TypeError, AttributeError) as exc:
            raise AsrAdapterError("ASR_WINDOW_INVALID", "El payload ASR no expone longitud.") from exc
        if payload_len != sample_count:
            raise AsrAdapterError(
                "ASR_WINDOW_INVALID",
                "sampleCount no coincide con la longitud del payload ASR.",
            )
        return payload

    @staticmethod
    def _finite_seconds(value: object, label: str) -> float:
        try:
            parsed = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise AsrAdapterError("ASR_RESULT_INVALID", f"Timestamp ASR inválido: {label}.") from exc
        if not math.isfinite(parsed) or parsed < 0:
            raise AsrAdapterError("ASR_RESULT_INVALID", f"Timestamp ASR inválido: {label}.")
        return parsed

    def _normalize_segments(self, raw_segments: object) -> tuple[AsrSegment, ...]:
        if raw_segments is None:
            return ()
        try:
            items = list(raw_segments)  # type: ignore[arg-type]
        except TypeError as exc:
            raise AsrAdapterError("ASR_RESULT_INVALID", "El provider ASR devolvió segmentos inválidos.") from exc

        normalized: list[AsrSegment] = []
        for item in items:
            text = str(getattr(item, "text", "") or "").strip()
            if not text:
                continue
            start = self._finite_seconds(getattr(item, "start", 0.0), "segment.start")
            end = self._finite_seconds(getattr(item, "end", start), "segment.end")
            if end < start:
                raise AsrAdapterError("ASR_RESULT_INVALID", "segment.end no puede preceder segment.start.")
            language_value = str(getattr(item, "language", "") or "").strip().lower()
            language = language_value or None
            words: list[AsrWord] = []
            for word in getattr(item, "words", ()) or ():
                word_text = str(getattr(word, "text", "") or "").strip()
                if not word_text:
                    continue
                word_start = self._finite_seconds(getattr(word, "start", 0.0), "word.start")
                word_end = self._finite_seconds(getattr(word, "end", word_start), "word.end")
                if word_end < word_start:
                    raise AsrAdapterError("ASR_RESULT_INVALID", "word.end no puede preceder word.start.")
                words.append(AsrWord(word_start * 1000.0, word_end * 1000.0, word_text))
            normalized.append(
                AsrSegment(
                    start_ms=start * 1000.0,
                    end_ms=end * 1000.0,
                    text=text,
                    language=language,
                    words=tuple(words),
                )
            )
        return tuple(normalized)

    def invoke(self, request: object) -> AsrResult:
        provider = self._provider
        if provider is None:
            raise AsrAdapterError("ASR_NOT_LOADED", "El adapter ASR no está cargado.")

        request_id = getattr(request, "request_id", None)
        frame = getattr(request, "frame", None)
        if not isinstance(request_id, str) or not request_id.strip() or frame is None:
            raise AsrAdapterError("ASR_REQUEST_INVALID", "request_id y frame son obligatorios.")
        utterance_id, source_language, final = self._request_metadata(request)
        payload = self._validate_window(frame)

        started_ns = int(self._clock_ns())
        if final and callable(getattr(provider, "transcribe_final", None)):
            raw_segments = provider.transcribe_final(payload, source_language)  # type: ignore[attr-defined]
        else:
            transcribe = getattr(provider, "transcribe", None)
            if not callable(transcribe):
                raise AsrAdapterError("ASR_PROVIDER_INVALID", "El provider no implementa transcribe().")
            raw_segments = transcribe(payload, source_language)
            if final:
                finish = getattr(provider, "finish_utterance", None)
                if callable(finish):
                    finish()
        finished_ns = int(self._clock_ns())

        segments = self._normalize_segments(raw_segments)
        text = " ".join(segment.text for segment in segments).strip()
        detected_language = next(
            (segment.language for segment in segments if segment.language),
            None,
        )
        if detected_language is None and source_language != "auto":
            detected_language = source_language

        sample_count = int(getattr(frame, "sample_count"))
        audio_duration_ms = sample_count / 16000.0 * 1000.0
        elapsed_ms = max(0, finished_ns - started_ns) / 1_000_000.0
        rtf = elapsed_ms / audio_duration_ms if audio_duration_ms > 0 else 0.0
        media_start_ns = int(getattr(frame, "media_start_ns"))
        media_end_ns = media_start_ns + int(getattr(frame, "duration_ns"))

        return AsrResult(
            request_id=request_id.strip(),
            utterance_id=utterance_id,
            sequence_id=int(getattr(frame, "sequence_id")),
            media_start_ns=media_start_ns,
            media_end_ns=media_end_ns,
            engine_id=self.engine_id,
            source_language=source_language,
            detected_language=detected_language,
            final=final,
            text=text,
            segments=segments,
            metrics=AsrMetrics(elapsed_ms, audio_duration_ms, rtf),
        )


class WhisperAsrAdapter(LegacyAsrAdapter):
    provider_id = "faster-whisper"
    engine_id = "whisper"


class MoonshineAsrAdapter(LegacyAsrAdapter):
    provider_id = "moonshine"
    engine_id = "moonshine"


class SherpaZipformerAsrAdapter(LegacyAsrAdapter):
    provider_id = "sherpa-onnx"
    engine_id = "sherpa-zipformer"
