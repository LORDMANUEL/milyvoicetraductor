"""Proveedor Vosk/Kaldi ligero para el perfil Legacy del Engine Hub."""

from __future__ import annotations

import gc
import json
import struct
from pathlib import Path
from typing import Sequence

from .cpu_budget import CpuBudget, detect_cpu_budget
from .optional_providers import OptionalProviderRuntimeError
from .providers import AsrProvider, AsrSegment, AsrWord


class VoskAsr(AsrProvider):
    """ASR local CPU con modelo Vosk mantenido residente entre segmentos."""

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget: CpuBudget | None = None,
        word_timestamps: bool = False,
    ) -> None:
        self.model_path = Path(model_path)
        self.compute_profile = compute_profile
        self.cpu_budget = cpu_budget or detect_cpu_budget()
        self.word_timestamps = bool(word_timestamps)
        self._model = None
        self._vosk = None
        self.selected_device = "cpu"
        self.fallback_used = compute_profile == "gpu"
        self.fallback_reason = (
            "Vosk utiliza CPU; se ignoró el perfil GPU." if compute_profile == "gpu" else ""
        )

    def _load(self):
        if self._model is not None:
            return self._model
        if not self.model_path.is_dir():
            raise OptionalProviderRuntimeError(
                "VOSK_MODEL_MISSING",
                "El pack Vosk no contiene una carpeta de modelo válida.",
            )
        try:
            import vosk
        except ImportError as exc:
            raise OptionalProviderRuntimeError(
                "VOSK_RUNTIME_MISSING",
                "Vosk no está instalado en este runtime.",
            ) from exc
        try:
            set_log_level = getattr(vosk, "SetLogLevel", None)
            if callable(set_log_level):
                set_log_level(-1)
            self._model = vosk.Model(str(self.model_path))
            self._vosk = vosk
        except Exception as exc:
            raise OptionalProviderRuntimeError(
                "VOSK_MODEL_LOAD",
                "Vosk no pudo abrir el modelo seleccionado.",
            ) from exc
        return self._model

    @staticmethod
    def _pcm16(samples: Sequence[float]) -> bytes:
        return b"".join(
            struct.pack(
                "<h",
                max(-32768, min(32767, round(float(value) * 32767.0))),
            )
            for value in samples
        )

    def transcribe(
        self, samples: Sequence[float], source_language: str
    ) -> list[AsrSegment]:
        if not samples:
            return []
        model = self._load()
        assert self._vosk is not None
        try:
            recognizer = self._vosk.KaldiRecognizer(model, 16000)
            set_words = getattr(recognizer, "SetWords", None)
            if callable(set_words):
                set_words(self.word_timestamps)
            recognizer.AcceptWaveform(self._pcm16(samples))
            payload = json.loads(recognizer.FinalResult() or "{}")
        except Exception as exc:
            raise OptionalProviderRuntimeError(
                "VOSK_EXECUTION",
                "Vosk no pudo procesar el fragmento de audio.",
            ) from exc

        text = str(payload.get("text", "") or "").strip()
        if not text:
            return []
        words = (
            tuple(
                AsrWord(
                    start=float(item.get("start", 0.0) or 0.0),
                    end=float(item.get("end", 0.0) or 0.0),
                    text=str(item.get("word", "") or "").strip(),
                )
                for item in (payload.get("result") or [])
                if str(item.get("word", "") or "").strip()
            )
            if self.word_timestamps
            else ()
        )
        language = "en" if source_language == "auto" else source_language
        return [
            AsrSegment(
                start=0.0,
                end=len(samples) / 16000.0,
                text=text,
                language=language,
                words=words,
            )
        ]

    def unload(self) -> None:
        self._model = None
        self._vosk = None
        gc.collect()
