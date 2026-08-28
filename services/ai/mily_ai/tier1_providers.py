"""Adaptadores Tier 1 aislados para las rutas bidireccionales de MilyVoice 2.1.

Los proveedores base permanecen estables. Esta capa añade únicamente el
contrato de idioma necesario para ES↔EN/ZH sin modificar los perfiles Lite.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .cpu_budget import CpuBudget
from .providers import (
    AsrSegment,
    FasterWhisperAsr,
    M2M100CTranslate2Translator,
)

_TIER1_LANGUAGES = {"es", "en", "zh"}


class Tier1FasterWhisperAsr(FasterWhisperAsr):
    """Faster-Whisper con warm-up explícito para español además de EN/ZH."""

    def warm_up(self, source_language: str = "en") -> None:
        if self._warmed:
            return
        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("numpy no está instalado") from exc
        model = self._load()
        language = source_language if source_language in _TIER1_LANGUAGES else "en"
        segments, _info = model.transcribe(
            np.zeros(16000, dtype=np.float32),
            language=language,
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
            word_timestamps=False,
            temperature=0.0,
        )
        list(segments)
        self._warmed = True

    def transcribe(
        self, samples: Sequence[float], source_language: str
    ) -> list[AsrSegment]:
        # La implementación base ya pasa cualquier idioma explícito a Whisper.
        # El protocolo garantiza aquí auto|es|en|zh.
        return super().transcribe(samples, source_language)


class TargetAwareM2M100CTranslate2Translator(M2M100CTranslate2Translator):
    """M2M100 CT2 con token de destino fijado por sesión Tier 1."""

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget: CpuBudget | None = None,
        *,
        target_language: str = "es",
    ):
        super().__init__(model_path, compute_profile, cpu_budget=cpu_budget)
        normalized = str(target_language or "es").strip().lower()
        if normalized not in _TIER1_LANGUAGES:
            raise ValueError("Destino M2M100 fuera de Tier 1")
        self.target_language = normalized

    def warm_up(self) -> None:
        if self._warmed:
            return
        source_language = "es" if self.target_language in {"en", "zh"} else "en"
        sample = "Hola." if source_language == "es" else "Hello."
        self.translate(sample, source_language)
        self._warmed = True

    def translate(self, text: str, source_language: str) -> str:
        if not text.strip():
            return ""
        self._load()
        assert self._translator is not None and self._tokenizer is not None
        normalized_source = str(source_language or "en").strip().lower()
        if normalized_source not in _TIER1_LANGUAGES:
            normalized_source = "en"
        self._tokenizer.src_lang = normalized_source
        source = self._tokenizer.convert_ids_to_tokens(self._tokenizer.encode(text))
        target_prefix = [self._tokenizer.lang_code_to_token[self.target_language]]
        results = self._translator.translate_batch(
            [source],
            target_prefix=[target_prefix],
            beam_size=1,
            return_scores=False,
            max_decoding_length=self._decoding_limit(len(source)),
        )
        target = results[0].hypotheses[0][1:]
        token_ids = self._tokenizer.convert_tokens_to_ids(target)
        return self._tokenizer.decode(token_ids, skip_special_tokens=True).strip()
