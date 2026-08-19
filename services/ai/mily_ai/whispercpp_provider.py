"""Ubicación segura del bridge whisper.cpp incluido por MilyVoice."""

from __future__ import annotations

import os
from pathlib import Path

from .optional_providers import OptionalProviderRuntimeError
from .safe_optional_providers import WhisperCppBridgeAsr


class BundledWhisperCppBridgeAsr(WhisperCppBridgeAsr):
    """Usa el bridge del instalador sin exigir variables manuales al usuario."""

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget=None,
        word_timestamps: bool = False,
        **kwargs,
    ):
        requested = str(compute_profile or "auto").strip().lower()
        if requested == "gpu":
            requested = "vulkan"
        parent_profile = (
            "gpu"
            if requested in {"cuda", "vulkan", "openvino"}
            else requested
        )
        super().__init__(
            model_path,
            parent_profile,
            cpu_budget=cpu_budget,
            word_timestamps=word_timestamps,
            **kwargs,
        )
        if requested in {"cpu", "cuda", "vulkan", "openvino"}:
            self.backend = requested
            self.selected_device = requested

    def _bridge(self) -> Path:
        configured = os.environ.get("MILY_WHISPER_CPP_BRIDGE", "").strip()
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        candidates = [
            Path(configured) if configured else None,
            (
                Path(local_app_data)
                / "MilyVoiceTraductor"
                / "bridge"
                / "milyvoice-bridge.exe"
                if local_app_data
                else None
            ),
            self.model_path / "milyvoice-bridge.exe",
            self.model_path / "milyvoice-bridge",
            self.model_path / "mily-whispercpp-bridge.exe",
            self.model_path / "mily-whispercpp-bridge",
        ]
        for candidate in candidates:
            if candidate is not None and candidate.is_file():
                return candidate
        raise OptionalProviderRuntimeError(
            "WHISPER_CPP_BRIDGE_MISSING",
            "No se encontró el bridge whisper.cpp incluido por MilyVoice.",
        )
