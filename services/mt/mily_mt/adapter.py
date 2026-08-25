"""Provider-neutral MT adapters for MilyVoice 3."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import monotonic_ns
from typing import Any, Callable, Mapping

from mily_linguistic import analyze_source_target_fidelity, analyze_translation_quality


class MtAdapterError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class MtResult:
    request_id: str
    utterance_id: str
    engine_id: str
    provider_id: str
    source_language: str
    target_language: str
    source_text: str
    target_text: str
    accepted: bool
    reason: str
    quality: object
    fidelity: object
    elapsed_ms: float


ProviderBuilder = Callable[[dict[str, Any], Path, str, object], object]
CpuBudgetBuilder = Callable[[str, int | None], object]


class BaseMtAdapter:
    engine_id = ""
    provider_id = ""
    source_language = ""
    target_language = ""

    def __init__(
        self,
        *,
        provider_builder: ProviderBuilder | None = None,
        cpu_budget_builder: CpuBudgetBuilder | None = None,
        clock_ns: Callable[[], int] | None = None,
    ) -> None:
        self._provider_builder = provider_builder
        self._cpu_budget_builder = cpu_budget_builder
        self._clock_ns = clock_ns or monotonic_ns
        self._provider: object | None = None

    @staticmethod
    def _config_dict(config: Mapping[str, object] | None) -> dict[str, object]:
        if config is None:
            return {}
        if not isinstance(config, Mapping):
            raise MtAdapterError("MT_CONFIG_INVALID", "La configuración MT debe ser un mapping")
        return dict(config)

    def _builders(self) -> tuple[ProviderBuilder, CpuBudgetBuilder]:
        provider_builder = self._provider_builder
        budget_builder = self._cpu_budget_builder
        if provider_builder is None:
            from mily_ai.provider_factory import build_translation_provider

            provider_builder = build_translation_provider
        if budget_builder is None:
            from mily_ai.cpu_budget import detect_cpu_budget

            budget_builder = detect_cpu_budget
        return provider_builder, budget_builder

    def load(self, config: Mapping[str, object] | None = None) -> None:
        if self._provider is not None:
            return
        payload = self._config_dict(config)
        model_path_raw = str(payload.get("modelPath") or "").strip()
        if not model_path_raw:
            raise MtAdapterError("MT_MODEL_PATH_REQUIRED", "MT requiere modelPath")

        raw_component = payload.get("component") or {}
        if not isinstance(raw_component, Mapping):
            raise MtAdapterError("MT_COMPONENT_INVALID", "component debe ser un mapping")
        component = dict(raw_component)

        declared_provider = str(component.get("provider") or "").strip().lower()
        if declared_provider and declared_provider != self.provider_id:
            raise MtAdapterError(
                "MT_PROVIDER_CONFLICT",
                f"El adapter {self.engine_id} requiere provider {self.provider_id}",
            )

        declared_source = str(component.get("sourceLanguage") or "").strip().lower()
        declared_target = str(component.get("targetLanguage") or "").strip().lower()
        if declared_source and declared_source != self.source_language:
            raise MtAdapterError(
                "MT_ROUTE_CONFLICT",
                f"El adapter {self.engine_id} requiere sourceLanguage={self.source_language}",
            )
        if declared_target and declared_target != self.target_language:
            raise MtAdapterError(
                "MT_ROUTE_CONFLICT",
                f"El adapter {self.engine_id} requiere targetLanguage={self.target_language}",
            )

        component["provider"] = self.provider_id
        if self.provider_id == "marian-ct2":
            component.setdefault("sourceLanguage", self.source_language)
            component.setdefault("targetLanguage", self.target_language)

        compute_profile = str(payload.get("computeProfile") or "auto").strip().lower() or "auto"
        cpu_profile = str(payload.get("cpuProfile") or "balanced").strip().lower() or "balanced"
        physical_raw = payload.get("physicalCores")
        physical_cores: int | None
        if physical_raw is None:
            physical_cores = None
        elif isinstance(physical_raw, bool):
            raise MtAdapterError("MT_PHYSICAL_CORES_INVALID", "physicalCores debe ser entero positivo")
        else:
            try:
                physical_cores = int(physical_raw)
            except (TypeError, ValueError) as exc:
                raise MtAdapterError(
                    "MT_PHYSICAL_CORES_INVALID", "physicalCores debe ser entero positivo"
                ) from exc
            if physical_cores <= 0:
                raise MtAdapterError(
                    "MT_PHYSICAL_CORES_INVALID", "physicalCores debe ser entero positivo"
                )

        provider_builder, budget_builder = self._builders()
        cpu_budget = budget_builder(cpu_profile, physical_cores)
        self._provider = provider_builder(
            component,
            Path(model_path_raw),
            compute_profile,
            cpu_budget,
        )

    @staticmethod
    def _required_text(value: object, field: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise MtAdapterError("MT_INPUT_INVALID", f"{field} es obligatorio")
        return text

    def _validate_input(self, frame: object) -> tuple[str, str, str]:
        if frame is None:
            raise MtAdapterError("MT_INPUT_INVALID", "Falta PreparedTranslationInput")
        try:
            text = self._required_text(getattr(frame, "text"), "text")
            source = self._required_text(getattr(frame, "source_language"), "source_language").lower()
            target = self._required_text(getattr(frame, "target_language"), "target_language").lower()
            segments = getattr(frame, "segments")
            terminology = getattr(frame, "terminology")
            context = getattr(frame, "context")
        except (AttributeError, TypeError) as exc:
            raise MtAdapterError("MT_INPUT_INVALID", "Entrada Linguistic inválida") from exc

        if source != self.source_language or target != self.target_language:
            raise MtAdapterError(
                "MT_INPUT_INVALID",
                f"Ruta inválida para {self.engine_id}: {source}->{target}",
            )
        if not isinstance(segments, tuple) or not isinstance(terminology, tuple) or not isinstance(context, tuple):
            raise MtAdapterError("MT_INPUT_INVALID", "Entrada Linguistic inválida")
        return text, source, target

    @staticmethod
    def _utterance_id(metadata: object) -> str:
        if not isinstance(metadata, Mapping):
            raise MtAdapterError("MT_METADATA_INVALID", "metadata debe ser mapping")
        utterance_id = str(metadata.get("utteranceId") or "").strip()
        if not utterance_id:
            raise MtAdapterError("MT_METADATA_INVALID", "utteranceId es obligatorio")
        return utterance_id

    def invoke(self, request: object) -> MtResult:
        provider = self._provider
        if provider is None:
            raise MtAdapterError("MT_NOT_LOADED", "El adapter MT no está cargado")
        try:
            request_id = self._required_text(getattr(request, "request_id"), "request_id")
            frame = getattr(request, "frame")
            metadata = getattr(request, "metadata")
        except AttributeError as exc:
            raise MtAdapterError("MT_REQUEST_INVALID", "Request MT inválido") from exc

        text, source, target = self._validate_input(frame)
        utterance_id = self._utterance_id(metadata)
        translator = getattr(provider, "translate", None)
        if not callable(translator):
            raise MtAdapterError("MT_PROVIDER_INVALID", "El provider no implementa translate")

        started = int(self._clock_ns())
        translated = str(translator(text, source) or "").strip()
        finished = int(self._clock_ns())
        elapsed_ms = max(0.0, (finished - started) / 1_000_000.0)

        quality = analyze_translation_quality(translated)
        fidelity = analyze_source_target_fidelity(text, translated, source, target)
        accepted = bool(quality.passed and fidelity.passed)
        if not fidelity.passed:
            reason = str(fidelity.reason)
        elif not quality.passed:
            reason = str(quality.reason)
        else:
            reason = "OK"

        return MtResult(
            request_id=request_id,
            utterance_id=utterance_id,
            engine_id=self.engine_id,
            provider_id=self.provider_id,
            source_language=source,
            target_language=target,
            source_text=text,
            target_text=translated,
            accepted=accepted,
            reason=reason,
            quality=quality,
            fidelity=fidelity,
            elapsed_ms=round(elapsed_ms, 6),
        )

    def health(self) -> bool:
        return self._provider is not None

    def unload(self) -> None:
        provider = self._provider
        self._provider = None
        if provider is None:
            return
        unload = getattr(provider, "unload", None)
        if callable(unload):
            unload()


class MarianEnEsMtAdapter(BaseMtAdapter):
    engine_id = "marian-en-es"
    provider_id = "marian-ct2"
    source_language = "en"
    target_language = "es"


class MarianZhEsCascadeMtAdapter(BaseMtAdapter):
    engine_id = "marian-zh-es"
    provider_id = "marian-cascade-ct2"
    source_language = "zh"
    target_language = "es"
