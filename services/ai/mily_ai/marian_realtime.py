"""Decodificación Marian/CTranslate2 endurecida para tiempo real.

El primer pase mantiene greedy search para latencia. Si el modelo pequeño entra
en un bucle o pierde información crítica detectable (números/negación EN→ES), se
ejecuta un segundo pase acotado antes de exponer la traducción.
"""

from __future__ import annotations

from .optional_providers import (
    CTranslate2MarianTranslator as _BaseMarianTranslator,
    OptionalProviderRuntimeError,
)
from .translation_quality import (
    analyze_source_target_fidelity,
    analyze_translation_quality,
    non_repetitive_sentence_prefix,
)


class CTranslate2RealtimeMarianTranslator(_BaseMarianTranslator):
    """Marian INT8 con guardas de repetición y fidelidad crítica."""

    repetition_penalty = 1.12
    no_repeat_ngram_size = 3

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

    def _fidelity(self, source: str, target: str, source_language: str):
        return analyze_source_target_fidelity(
            source,
            target,
            source_language,
            self.target_language,
        )

    def translate(self, text: str, source_language: str) -> str:
        if not text.strip():
            return ""
        if source_language not in {self.source_language, "auto"}:
            raise OptionalProviderRuntimeError(
                "MARIAN_ROUTE_MISMATCH",
                "El modelo directo no admite esta dirección de traducción.",
            )

        effective_source = self.source_language if source_language == "auto" else source_language
        translated = self._decode(
            text,
            beam_size=1,
            repetition_penalty=self.repetition_penalty,
            tighter_limit=False,
        )
        quality = analyze_translation_quality(translated)
        fidelity = self._fidelity(text, translated, effective_source)
        if quality.passed and fidelity.passed:
            return translated

        # El segundo pase solo se paga cuando el greedy falla una guarda barata.
        retry = self._decode(
            text,
            beam_size=2,
            repetition_penalty=1.20,
            tighter_limit=True,
        )
        retry_quality = analyze_translation_quality(retry)
        retry_fidelity = self._fidelity(text, retry, effective_source)
        if retry_quality.passed and retry_fidelity.passed:
            return retry

        prefix = non_repetitive_sentence_prefix(retry or translated)
        if (
            prefix
            and analyze_translation_quality(prefix).passed
            and self._fidelity(text, prefix, effective_source).passed
        ):
            return prefix

        fidelity_failure = retry_fidelity if not retry_fidelity.passed else fidelity
        if not fidelity_failure.passed:
            raise OptionalProviderRuntimeError(
                "MARIAN_FIDELITY",
                "La traducción local perdió información crítica y fue descartada para evitar mostrar una frase incorrecta.",
            )

        raise OptionalProviderRuntimeError(
            "MARIAN_REPETITION",
            "El traductor local produjo una repetición insegura y la frase fue descartada.",
        )
