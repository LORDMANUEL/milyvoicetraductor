"""Ubicación segura del bridge whisper.cpp incluido por MilyVoice."""

from __future__ import annotations

import os
from pathlib import Path

from .optional_providers import OptionalProviderRuntimeError
from .safe_optional_providers import WhisperCppBridgeAsr


class BundledWhisperCppBridgeAsr(WhisperCppBridgeAsr):
    """Usa el bridge del instalador sin exigir variables manuales al usuario."""

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
