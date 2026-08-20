"""Decodificación Marian/CTranslate2 endurecida para tiempo real.

El primer pase mantiene greedy search para latencia. Si el modelo pequeño entra
en un bucle o pierde información crítica detectable (números/negación EN→ES), se
ejecutan rescates acotados antes de exponer la traducción.
"""

from __future__ import annotations

import re

from .optional_providers import (
    CTranslate2MarianTranslator as _BaseMarianTranslator,
    OptionalProviderRuntimeError,
)
from .translation_quality import (
    analyze_source_target_fidelity,
    analyze_translation_quality,
    non_repetitive_ngram_prefix,
    non_repetitive_sentence_prefix,
)

_CONTRACTION_EXPANSIONS = (
    (re.compile(r"\bwon['’]t\b", re.IGNORECASE), "will not"),
    (re.compile(r"\bcan['’]t\b", re.IGNORECASE), "cannot"),
    (re.compile(r"\bdon['’]t\b", re.IGNORECASE), "do not"),
    (re.compile(r"\bdoesn['’]t\b", re.IGNORECASE), "does not"),
    (re.compile(r"\bdidn['’]t\b", re.IGNORECASE), "did not"),
    (re.compile(r"\bisn['’]t\b", re.IGNORECASE), "is not"),
    (re.compile(r"\baren['’]t\b", re.IGNORECASE), "are not"),
    (re.compile(r"\bwasn['’]t\b", re.IGNORECASE), "was not"),
    (re.compile(r"\bweren['’]t\b", re.IGNORECASE), "were not"),
    (re.compile(r"\bshouldn['’]t\b", re.IGNORECASE), "should not"),
    (re.compile(r"\bwouldn['’]t\b", re.IGNORECASE), "would not"),
    (re.compile(r"\bcouldn['’]t\b", re.IGNORECASE), "could not"),
    (re.compile(r"\bmustn['’]t\b", re.IGNORECASE), "must not"),
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
        no_repeat_ngram_size: int | None = None,
        severe_limit: bool = False,
    ) -> str:
        self._load()
        assert self._translator is not None
        assert self._source_sp is not None and self._target_sp is not None

        source_tokens = self._source_sp.encode(text.strip(), out_type=str)
        decoding_limit = self._decoding_limit(len(source_tokens))
        if severe_limit:
            decoding_limit = min(
                decoding_limit,
                max(12, round(len(source_tokens) * 1.35) + 4),
            )
        elif tighter_limit:
            decoding_limit = min(
                decoding_limit,
                max(12, round(len(source_tokens) * 1.6) + 6),
            )
        result = self._translator.translate_batch(
            [source_tokens],
            beam_size=beam_size,
            return_scores=False,
            repetition_penalty=repetition_penalty,
            no_repeat_ngram_size=(
                self.no_repeat_ngram_size
                if no_repeat_ngram_size is None
                else no_repeat_ngram_size
            ),
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

    @staticmethod
    def _quality_rescue_source(text: str, source_language: str) -> str:
        """Expande contracciones inglesas solo para el último decode de rescate.

        No altera el texto que se usa para validar fidelidad. Sirve para que Marian
        vea la negación de forma inequívoca si los tres pases realtime la perdieron.
        """

        if source_language != "en":
            return text
        expanded = text
        for pattern, replacement in _CONTRACTION_EXPANSIONS:
            expanded = pattern.sub(replacement, expanded)
        return expanded

    def _safe_repetition_prefixes(
        self,
        source: str,
        source_language: str,
        *outputs: str,
    ) -> list[str]:
        candidates: list[str] = []
        for output in outputs:
            if not output:
                continue
            for builder in (
                non_repetitive_sentence_prefix,
                non_repetitive_ngram_prefix,
            ):
                prefix = builder(output)
                if not prefix:
                    continue
                if not analyze_translation_quality(prefix).passed:
                    continue
                if not self._fidelity(source, prefix, source_language).passed:
                    continue
                if prefix not in candidates:
                    candidates.append(prefix)
        return candidates

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

        # Una repetición puede ocurrir dentro de una sola oración. En ese caso se
        # conserva únicamente un prefijo que siga preservando números/negaciones.
        prefixes = self._safe_repetition_prefixes(
            text,
            effective_source,
            retry,
            translated,
        )
        if prefixes:
            return max(prefixes, key=len)

        # Tercer pase: bloqueo fuerte de bigramas y longitud corta para cortar loops.
        rescue = self._decode(
            text,
            beam_size=3,
            repetition_penalty=1.32,
            tighter_limit=True,
            no_repeat_ngram_size=2,
            severe_limit=True,
        )
        rescue_quality = analyze_translation_quality(rescue)
        rescue_fidelity = self._fidelity(text, rescue, effective_source)
        if rescue_quality.passed and rescue_fidelity.passed:
            return rescue

        rescue_prefixes = self._safe_repetition_prefixes(
            text,
            effective_source,
            rescue,
        )
        if rescue_prefixes:
            return max(rescue_prefixes, key=len)

        # Último recurso de FIDELIDAD: Marian OPUS usa beam=4 como configuración de
        # calidad. Se ejecuta únicamente tras fallar los tres pases anteriores. No
        # relaja ninguna guarda: el resultado debe pasar repetición y fidelidad contra
        # el texto ORIGINAL antes de exponerse.
        quality_source = self._quality_rescue_source(text, effective_source)
        quality_rescue = self._decode(
            quality_source,
            beam_size=4,
            repetition_penalty=1.10,
            tighter_limit=False,
            no_repeat_ngram_size=3,
        )
        quality_rescue_quality = analyze_translation_quality(quality_rescue)
        quality_rescue_fidelity = self._fidelity(
            text,
            quality_rescue,
            effective_source,
        )
        if quality_rescue_quality.passed and quality_rescue_fidelity.passed:
            return quality_rescue

        quality_prefixes = self._safe_repetition_prefixes(
            text,
            effective_source,
            quality_rescue,
        )
        if quality_prefixes:
            return max(quality_prefixes, key=len)

        fidelity_failure = next(
            (
                item
                for item in (
                    quality_rescue_fidelity,
                    rescue_fidelity,
                    retry_fidelity,
                    fidelity,
                )
                if not item.passed
            ),
            None,
        )
        if fidelity_failure is not None:
            raise OptionalProviderRuntimeError(
                "MARIAN_FIDELITY",
                "La traducción local perdió información crítica y fue descartada para evitar mostrar una frase incorrecta.",
            )

        raise OptionalProviderRuntimeError(
            "MARIAN_REPETITION",
            "El traductor local produjo una repetición insegura y la frase fue descartada.",
        )
