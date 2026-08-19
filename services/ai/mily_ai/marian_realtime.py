"""Decodificación Marian/CTranslate2 endurecida para tiempo real.

El primer pase mantiene greedy search para latencia. Si el modelo pequeño entra
en un bucle, se ejecuta un segundo pase acotado y se conserva únicamente un
prefijo sano antes de exponer la traducción. BetaAlpha puede además medir el
compute type más rápido de CTranslate2 para la CPU concreta y persistirlo.
"""

from __future__ import annotations

import time

from .compute_router import load_backend_with_fallback
from .ctranslate2_tuning import CTranslate2ComputeTuner
from .optional_providers import (
    CTranslate2MarianTranslator as _BaseMarianTranslator,
    OptionalProviderRuntimeError,
)
from .translation_quality import (
    analyze_translation_quality,
    non_repetitive_sentence_prefix,
)


class CTranslate2RealtimeMarianTranslator(_BaseMarianTranslator):
    """Marian realtime con calidad protegida y tuning opcional por CPU."""

    repetition_penalty = 1.12
    no_repeat_ngram_size = 3

    def __init__(self, *args, auto_tune_compute_type: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.auto_tune_compute_type = bool(
            auto_tune_compute_type
            or "betaalpha-" in str(self.model_path).replace("\\", "/").lower()
        )
        self.selected_compute_type: str | None = None
        self.compute_tuning_cached = False

    def _load(self) -> None:
        if self._translator is not None:
            return
        if not self.auto_tune_compute_type or self.compute_profile not in {"cpu", "auto"}:
            super()._load()
            return

        try:
            import ctranslate2
            import sentencepiece as spm
        except ImportError as exc:
            raise OptionalProviderRuntimeError(
                "MARIAN_RUNTIME_MISSING",
                "El runtime local no contiene CTranslate2/SentencePiece para OPUS-MT.",
            ) from exc

        cuda_count = 0
        if self.compute_profile == "auto":
            try:
                cuda_count = int(ctranslate2.get_cuda_device_count())
            except Exception:
                cuda_count = 0
        if cuda_count > 0:
            super()._load()
            return

        source_path = self._sentencepiece_file(
            ("source.spm", "source.model", "sentencepiece.source.model")
        )
        target_path = self._sentencepiece_file(
            ("target.spm", "target.model", "sentencepiece.target.model")
        )
        source_sp = spm.SentencePieceProcessor(model_file=str(source_path))
        target_sp = spm.SentencePieceProcessor(model_file=str(target_path))
        probe_text = "你好。" if self.source_language == "zh" else "Hello."
        probe_tokens = source_sp.encode(probe_text, out_type=str)

        try:
            supported = {
                str(item).strip().lower()
                for item in ctranslate2.get_supported_compute_types("cpu")
            }
        except Exception:
            supported = {"int8"}

        def factory(compute_type: str):
            return ctranslate2.Translator(
                str(self.model_path),
                device="cpu",
                compute_type=compute_type,
                inter_threads=1,
                intra_threads=max(1, self.cpu_budget.translation_threads),
            )

        def benchmark(translator, tokens) -> float:
            translator.translate_batch(
                [list(tokens)],
                beam_size=1,
                return_scores=False,
                max_decoding_length=min(24, self._decoding_limit(len(tokens))),
            )
            started = time.perf_counter()
            translator.translate_batch(
                [list(tokens)],
                beam_size=1,
                return_scores=False,
                max_decoding_length=min(24, self._decoding_limit(len(tokens))),
            )
            return max(0.001, (time.perf_counter() - started) * 1000.0)

        tuner = CTranslate2ComputeTuner()
        result = tuner.choose(
            model_path=self.model_path,
            source_language=self.source_language,
            supported=supported,
            budget=self.cpu_budget,
            translator_factory=factory,
            probe_tokens=probe_tokens,
            benchmark=benchmark,
        )

        def loader(device: str):
            if device != "cpu":
                return ctranslate2.Translator(
                    str(self.model_path),
                    device=device,
                    compute_type="auto",
                    inter_threads=1,
                    intra_threads=0,
                )
            return factory(result.compute_type)

        loaded = load_backend_with_fallback("cpu", 0, loader)
        self._translator = loaded.value
        self.selected_device = loaded.device
        self.fallback_used = loaded.fallback_used
        self.fallback_reason = loaded.reason
        self.selected_compute_type = result.compute_type
        self.compute_tuning_cached = result.cached
        self._source_sp = source_sp
        self._target_sp = target_sp

    def _decode(
        self,
        text: str,
        *,
        beam_size: int,
        repetition_penalty: float,
        tighter_limit: bool,
    ) -> str:
        self._load()
        assert self._translator is not None
        assert self._source_sp is not None and self._target_sp is not None

        source_tokens = self._source_sp.encode(text.strip(), out_type=str)
        decoding_limit = self._decoding_limit(len(source_tokens))
        if tighter_limit:
            decoding_limit = min(
                decoding_limit,
                max(12, round(len(source_tokens) * 1.6) + 6),
            )
        result = self._translator.translate_batch(
            [source_tokens],
            beam_size=beam_size,
            return_scores=False,
            repetition_penalty=repetition_penalty,
            no_repeat_ngram_size=self.no_repeat_ngram_size,
            max_decoding_length=decoding_limit,
        )[0]
        return self._target_sp.decode(result.hypotheses[0]).strip()

    def translate(self, text: str, source_language: str) -> str:
        if not text.strip():
            return ""
        if source_language not in {self.source_language, "auto"}:
            raise OptionalProviderRuntimeError(
                "MARIAN_ROUTE_MISMATCH",
                "El modelo directo no admite esta dirección de traducción.",
            )

        translated = self._decode(
            text,
            beam_size=1,
            repetition_penalty=self.repetition_penalty,
            tighter_limit=False,
        )
        quality = analyze_translation_quality(translated)
        if quality.passed:
            return translated

        retry = self._decode(
            text,
            beam_size=2,
            repetition_penalty=1.20,
            tighter_limit=True,
        )
        retry_quality = analyze_translation_quality(retry)
        if retry_quality.passed:
            return retry

        prefix = non_repetitive_sentence_prefix(retry or translated)
        if prefix and analyze_translation_quality(prefix).passed:
            return prefix

        raise OptionalProviderRuntimeError(
            "MARIAN_REPETITION",
            "El traductor local produjo una repetición insegura y la frase fue descartada.",
        )

    def unload(self) -> None:
        super().unload()
        self.selected_compute_type = None
