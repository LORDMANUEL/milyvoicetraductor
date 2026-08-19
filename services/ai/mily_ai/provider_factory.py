"""Factory central de proveedores ASR/MT del Engine Hub."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .cloud_providers import GoogleChirpV2Asr
from .cpu_budget import CpuBudget
from .moonshine_provider import MoonshineStreamingAsr
from .optional_providers import CTranslate2MarianTranslator, SherpaOnnxAsr
from .providers import (
    AsrProvider,
    FasterWhisperAsr,
    M2M100CTranslate2Translator,
    NllbTranslator,
    QwenTranslator,
    Translator,
)
from .vosk_provider import VoskAsr
from .whispercpp_provider import BundledWhisperCppBridgeAsr


@dataclass(slots=True)
class ProviderConfigurationError(RuntimeError):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


AsrBuilder = Callable[[Path, str, CpuBudget, bool], AsrProvider]
TranslationBuilder = Callable[[dict[str, Any], Path, str, CpuBudget], Translator]
_ALLOWED_BACKENDS = {
    "auto",
    "cpu",
    "cuda",
    "vulkan",
    "openvino",
    "directml",
    "windowsml",
    "cloud",
}


def normalize_backend(value: object) -> str:
    backend = str(value or "auto").strip().lower()
    if backend == "gpu":
        backend = "cuda"
    return backend if backend in _ALLOWED_BACKENDS else "auto"


def _asr_compute_profile(provider: str, backend: str) -> str:
    normalized = normalize_backend(backend)
    if provider == "whisper-cpp":
        return normalized
    if provider == "google-chirp":
        return "cloud" if normalized == "cloud" else normalized
    if provider == "faster-whisper":
        if normalized == "cuda":
            return "gpu"
        return normalized if normalized in {"auto", "cpu"} else "cpu"
    return "cpu"


def _translation_compute_profile(backend: str) -> str:
    normalized = normalize_backend(backend)
    if normalized == "cuda":
        return "gpu"
    return normalized if normalized == "auto" else "cpu"


def _asr_builder(cls):
    def build(
        model_path: Path,
        compute_profile: str,
        cpu_budget: CpuBudget,
        word_timestamps: bool,
    ) -> AsrProvider:
        return cls(
            model_path,
            compute_profile,
            cpu_budget=cpu_budget,
            word_timestamps=word_timestamps,
        )

    return build


ASR_BUILDERS: dict[str, AsrBuilder] = {
    "faster-whisper": _asr_builder(FasterWhisperAsr),
    "moonshine": _asr_builder(MoonshineStreamingAsr),
    "sherpa-onnx": _asr_builder(SherpaOnnxAsr),
    "whisper-cpp": _asr_builder(BundledWhisperCppBridgeAsr),
    "vosk": _asr_builder(VoskAsr),
    "google-chirp": _asr_builder(GoogleChirpV2Asr),
}


def _m2m100(
    _component: dict[str, Any],
    model_path: Path,
    compute_profile: str,
    cpu_budget: CpuBudget,
) -> Translator:
    return M2M100CTranslate2Translator(
        model_path,
        compute_profile,
        cpu_budget=cpu_budget,
    )


def _marian(
    component: dict[str, Any],
    model_path: Path,
    compute_profile: str,
    cpu_budget: CpuBudget,
) -> Translator:
    source = str(component.get("sourceLanguage", "")).strip().lower()
    target = str(component.get("targetLanguage", "")).strip().lower()
    if not source or not target:
        raise ProviderConfigurationError(
            "MARIAN_ROUTE_REQUIRED",
            "El proveedor Marian requiere sourceLanguage y targetLanguage.",
        )
    return CTranslate2MarianTranslator(
        model_path,
        compute_profile,
        cpu_budget=cpu_budget,
        source_language=source,
        target_language=target,
    )


def _qwen(
    _component: dict[str, Any],
    model_path: Path,
    compute_profile: str,
    _cpu_budget: CpuBudget,
) -> Translator:
    return QwenTranslator(model_path, compute_profile)


def _nllb(
    _component: dict[str, Any],
    model_path: Path,
    compute_profile: str,
    _cpu_budget: CpuBudget,
) -> Translator:
    return NllbTranslator(model_path, compute_profile)


TRANSLATION_BUILDERS: dict[str, TranslationBuilder] = {
    "m2m100-ct2": _m2m100,
    "marian-ct2": _marian,
    "qwen": _qwen,
    "nllb": _nllb,
}


def build_asr_provider(
    component: dict[str, Any],
    model_path: Path,
    compute_profile: str,
    cpu_budget: CpuBudget,
    word_timestamps: bool,
) -> AsrProvider:
    provider = str(component.get("provider", "")).strip().lower()
    builder = ASR_BUILDERS.get(provider)
    if builder is None:
        raise ProviderConfigurationError(
            "ASR_PROVIDER_UNSUPPORTED",
            f"Proveedor ASR no soportado: {provider or 'vacío'}",
        )
    return builder(
        Path(model_path),
        _asr_compute_profile(provider, compute_profile),
        cpu_budget,
        bool(word_timestamps),
    )


def build_translation_provider(
    component: dict[str, Any],
    model_path: Path,
    compute_profile: str,
    cpu_budget: CpuBudget,
) -> Translator:
    provider = str(component.get("provider", "")).strip().lower()
    builder = TRANSLATION_BUILDERS.get(provider)
    if builder is None:
        raise ProviderConfigurationError(
            "TRANSLATION_PROVIDER_UNSUPPORTED",
            f"Proveedor de traducción no soportado: {provider or 'vacío'}",
        )
    return builder(
        component,
        Path(model_path),
        _translation_compute_profile(compute_profile),
        cpu_budget,
    )
