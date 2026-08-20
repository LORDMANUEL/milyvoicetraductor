"""Conectores ASR cloud opcionales y explícitos del Engine Hub."""

from __future__ import annotations

import os
import struct
from pathlib import Path
from typing import Any, Sequence

from .cpu_budget import CpuBudget, detect_cpu_budget
from .optional_providers import OptionalProviderRuntimeError
from .providers import AsrProvider, AsrSegment


class GoogleChirpV2Asr(AsrProvider):
    """Google Chirp 3 V2; nunca sale a la red sin consentimiento explícito."""

    LANGUAGE_CODES = {
        "en": "en-US",
        "es": "es-ES",
        "zh": "cmn-Hans-CN",
        "auto": "auto",
    }

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget: CpuBudget | None = None,
        word_timestamps: bool = False,
        *,
        client: Any | None = None,
        speech_types: Any | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.compute_profile = compute_profile
        self.cpu_budget = cpu_budget or detect_cpu_budget()
        self.word_timestamps = bool(word_timestamps)
        self._client = client
        self._speech_types = speech_types
        self.selected_device = "cloud"
        self.fallback_used = False
        self.fallback_reason = ""

    @staticmethod
    def _pcm16(samples: Sequence[float]) -> bytes:
        return b"".join(
            struct.pack(
                "<h",
                max(-32768, min(32767, round(float(value) * 32767.0))),
            )
            for value in samples
        )

    def _load(self):
        if os.environ.get("MILY_GOOGLE_CHIRP_CONSENT") != "1":
            raise OptionalProviderRuntimeError(
                "GOOGLE_CHIRP_CONSENT_REQUIRED",
                "Google Chirp requiere consentimiento explícito porque el audio sale del equipo.",
            )
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
        if not project:
            raise OptionalProviderRuntimeError(
                "GOOGLE_CHIRP_NOT_CONFIGURED",
                "Google Chirp requiere un proyecto de Google Cloud configurado.",
            )
        region = os.environ.get("MILY_GOOGLE_CLOUD_REGION", "us").strip() or "us"
        if self._client is None or self._speech_types is None:
            try:
                from google.api_core.client_options import ClientOptions
                from google.cloud.speech_v2 import SpeechClient
                from google.cloud.speech_v2.types import cloud_speech
            except ImportError as exc:
                raise OptionalProviderRuntimeError(
                    "GOOGLE_CHIRP_RUNTIME_MISSING",
                    "El conector Google Cloud Speech no está instalado.",
                ) from exc
            try:
                self._client = SpeechClient(
                    client_options=ClientOptions(
                        api_endpoint=f"{region}-speech.googleapis.com"
                    )
                )
                self._speech_types = cloud_speech
            except Exception as exc:
                raise OptionalProviderRuntimeError(
                    "GOOGLE_CHIRP_NOT_CONFIGURED",
                    "Google Chirp no pudo abrir las credenciales configuradas.",
                ) from exc
        return self._client, self._speech_types, project, region

    def transcribe(
        self, samples: Sequence[float], source_language: str
    ) -> list[AsrSegment]:
        if not samples:
            return []
        client, cloud_speech, project, region = self._load()
        try:
            decoding = cloud_speech.ExplicitDecodingConfig(
                encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                audio_channel_count=1,
            )
            config = cloud_speech.RecognitionConfig(
                explicit_decoding_config=decoding,
                language_codes=[self.LANGUAGE_CODES.get(source_language, "en-US")],
                model="chirp_3",
            )
            request = cloud_speech.RecognizeRequest(
                recognizer=f"projects/{project}/locations/{region}/recognizers/_",
                config=config,
                content=self._pcm16(samples),
            )
            response = client.recognize(request=request)
        except OptionalProviderRuntimeError:
            raise
        except Exception as exc:
            raise OptionalProviderRuntimeError(
                "GOOGLE_CHIRP_EXECUTION",
                "Google Chirp no pudo procesar el fragmento de audio.",
            ) from exc

        texts: list[str] = []
        detected = source_language
        for result in getattr(response, "results", ()) or ():
            alternatives = getattr(result, "alternatives", ()) or ()
            if alternatives:
                text = str(getattr(alternatives[0], "transcript", "") or "").strip()
                if text:
                    texts.append(text)
            language_code = str(getattr(result, "language_code", "") or "")
            if language_code.startswith("cmn") or language_code.startswith("zh"):
                detected = "zh"
            elif language_code.startswith("es"):
                detected = "es"
            elif language_code.startswith("en"):
                detected = "en"
        text = " ".join(texts).strip()
        if not text:
            return []
        return [
            AsrSegment(
                start=0.0,
                end=len(samples) / 16000.0,
                text=text,
                language="en" if detected == "auto" else detected,
            )
        ]
