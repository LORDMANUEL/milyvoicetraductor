"""Cascada Marian CT2 para rutas Lite sin modelo directo promovido.

La cascada mantiene dos modelos pequeños residentes para priorizar latencia. Ambos
se descargan/validan como datos y se liberan explícitamente al cambiar de pack.
"""

from __future__ import annotations

import re
from pathlib import Path

from .cpu_budget import CpuBudget
from .marian_realtime import CTranslate2RealtimeMarianTranslator
from .optional_providers import OptionalProviderRuntimeError
from .providers import Translator
from .translation_quality import (
    analyze_source_target_fidelity,
    analyze_translation_quality,
)

_CLAUSE_SEPARATOR_RE = re.compile(r"\s*[,;:]+\s*")


class CTranslate2MarianCascadeTranslator(Translator):
    """ZH→EN→ES sobre dos traductores Marian CTranslate2 INT8.

    Es un fallback Lite transitorio hasta que un estudiante directo ZH→ES supere
    los mismos gates de calidad, memoria, RTF y latencia.
    """

    def __init__(
        self,
        model_path: Path,
        compute_profile: str,
        cpu_budget: CpuBudget,
        *,
        source_language: str = "zh",
        pivot_language: str = "en",
        target_language: str = "es",
    ):
        self.model_path = Path(model_path)
        self.source_language = source_language
        self.pivot_language = pivot_language
        self.target_language = target_language
        self._first = CTranslate2RealtimeMarianTranslator(
            self.model_path / "stage-1",
            compute_profile,
            cpu_budget=cpu_budget,
            source_language=source_language,
            target_language=pivot_language,
        )
        self._second = CTranslate2RealtimeMarianTranslator(
            self.model_path / "stage-2",
            compute_profile,
            cpu_budget=cpu_budget,
            source_language=pivot_language,
            target_language=target_language,
        )
        self.selected_device: str | None = None
        self.fallback_used = False
        self.fallback_reason = ""
        self._warmed = False

    def _sync_status(self) -> None:
        devices = {
            str(getattr(stage, "selected_device", "") or "unknown").lower()
            for stage in (self._first, self._second)
        }
        self.selected_device = devices.pop() if len(devices) == 1 else "cpu"
        self.fallback_used = any(
            bool(getattr(stage, "fallback_used", False))
            for stage in (self._first, self._second)
        )
        reasons = [
            str(getattr(stage, "fallback_reason", "") or "").strip()
            for stage in (self._first, self._second)
        ]
        self.fallback_reason = "; ".join(reason for reason in reasons if reason)[:80]

    @staticmethod
    def _pivot_clauses(pivot: str) -> list[str]:
        """Divide solo compuestos claros; nunca inventa ni reordena contenido."""

        clauses = [part.strip() for part in _CLAUSE_SEPARATOR_RE.split(pivot) if part.strip()]
        if not 2 <= len(clauses) <= 4:
            return []
        if any(len(clause.split()) < 2 for clause in clauses):
            return []
        return clauses

    def _translate_pivot_by_verified_clauses(self, pivot: str) -> str | None:
        """Rescata un compuesto cuando Marian falla la frase completa.

        Cada cláusula pasa por el mismo traductor endurecido. La concatenación se
        vuelve a validar contra el pivote COMPLETO, por lo que no se relajan números,
        negaciones ni guardas de repetición. Si algo no cuadra, no se usa el rescate.
        """

        clauses = self._pivot_clauses(pivot)
        if not clauses:
            return None

        translated_clauses: list[str] = []
        for clause in clauses:
            translated = self._second.translate(clause, self.pivot_language).strip()
            if not translated:
                return None
            translated_clauses.append(translated.rstrip(" .;,:"))

        combined = ". ".join(translated_clauses).strip()
        if combined and not combined.endswith("."):
            combined += "."
        quality = analyze_translation_quality(combined)
        fidelity = analyze_source_target_fidelity(
            pivot,
            combined,
            self.pivot_language,
            self.target_language,
        )
        if quality.passed and fidelity.passed:
            return combined
        return None

    def translate(self, text: str, source_language: str) -> str:
        if not text.strip():
            return ""
        if source_language not in {self.source_language, "auto"}:
            raise OptionalProviderRuntimeError(
                "MARIAN_CASCADE_ROUTE_MISMATCH",
                "La cascada Lite no admite esta dirección de traducción.",
            )
        pivot = self._first.translate(text, self.source_language)
        if not pivot.strip():
            return ""
        try:
            translated = self._second.translate(pivot, self.pivot_language)
        except OptionalProviderRuntimeError as exc:
            if exc.code not in {"MARIAN_FIDELITY", "MARIAN_REPETITION"}:
                raise
            translated = self._translate_pivot_by_verified_clauses(pivot)
            if translated is None:
                raise
        self._sync_status()
        return translated

    def warm_up(self) -> None:
        if self._warmed:
            return
        # Calienta cada etapa con una frase útil de SU idioma de entrada. No se
        # encadena la salida sintética del primer modelo: un saludo ZH demasiado
        # corto puede producir un pivote degenerado y disparar correctamente las
        # guardas de repetición EN→ES antes de que empiece el benchmark real.
        self._first.translate("请确认今天的会议安排。", self.source_language)
        self._second.translate(
            "Please confirm today's meeting schedule.", self.pivot_language
        )
        self._sync_status()
        self._warmed = True

    def unload(self) -> None:
        # Orden inverso de carga para soltar primero la última etapa activa.
        self._second.unload()
        self._first.unload()
        self.selected_device = None
        self.fallback_used = False
        self.fallback_reason = ""
        self._warmed = False
