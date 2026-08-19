"""Descubrimiento ligero de runtimes y backends realmente disponibles."""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeInventory:
    runtimes: frozenset[str]
    backends: frozenset[str]
    details: dict[str, str]


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def discover_runtime_inventory() -> RuntimeInventory:
    runtimes: set[str] = {"builtin"}
    backends: set[str] = {"cpu"}
    details: dict[str, str] = {"cpu": "available"}

    if _module_available("transformers") and _module_available("torch"):
        runtimes.add("transformers")

    if _module_available("moonshine_voice"):
        runtimes.add("moonshine")
    if _module_available("sherpa_onnx"):
        runtimes.add("sherpa-onnx")
    if _module_available("vosk"):
        runtimes.add("vosk")

    whisper_bridge = os.environ.get("MILY_WHISPER_CPP_BRIDGE", "").strip()
    if whisper_bridge and os.path.isfile(whisper_bridge):
        runtimes.add("whisper-cpp")
        details["whisperCppBridge"] = whisper_bridge
    else:
        details["whisperCppBridge"] = ""

    if _module_available("google.cloud.speech_v2") and os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS"
    ):
        runtimes.add("google-cloud")
        backends.add("cloud")

    try:
        import ctranslate2

        cuda_count = int(ctranslate2.get_cuda_device_count())
        details["ctranslate2CudaDevices"] = str(max(0, cuda_count))
        if cuda_count > 0:
            backends.add("cuda")
    except (ImportError, RuntimeError, OSError, ValueError):
        details["ctranslate2CudaDevices"] = "0"

    try:
        import onnxruntime as ort

        providers = set(ort.get_available_providers())
        details["onnxProviders"] = ",".join(sorted(providers))
        if "CUDAExecutionProvider" in providers:
            backends.add("cuda")
        if "DmlExecutionProvider" in providers:
            backends.add("directml")
            backends.add("windowsml")
        if "OpenVINOExecutionProvider" in providers:
            backends.add("openvino")
    except (ImportError, RuntimeError, OSError):
        details.setdefault("onnxProviders", "")

    if os.environ.get("MILY_VULKAN_AVAILABLE") == "1":
        backends.add("vulkan")
    return RuntimeInventory(
        runtimes=frozenset(runtimes),
        backends=frozenset(backends),
        details=details,
    )
