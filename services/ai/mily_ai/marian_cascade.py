"""Cascada Marian CT2 para rutas Lite sin modelo directo promovido.

La cascada mantiene dos modelos pequeños residentes para priorizar latencia. Ambos
se descargan/validan como datos y se liberan explícitamente al cambiar de pack.
"""

from __future__ import annotations

from pathlib import Path

from .cpu_budget import CpuBudget
from .optional_providers import CTranslate2MarianTranslator, OptionalProviderRuntimeError
from .providers import Translator


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
        self._first = CTranslate2MarianTranslator(
            self.model_path / "stage-1",
            compute_profile,
            cpu_budget=cpu_budget,
            source_language=source_language,
            target_language=pivot_language,
        )
        self._second = CTranslate2MarianTranslator(
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
        translated = self._second.translate(pivot, self.pivot_language)
        self._sync_status()
        return translated

    def warm_up(self) -> None:
        if self._warmed:
            return
        # Frase corta real en mandarín para que ambos modelos y tokenizadores
        # queden preparados antes de iniciar audio realtime.
        self.translate("你好。", self.source_language)
        self._warmed = True

    def unload(self) -> None:
        # Orden inverso de carga para soltar primero la última etapa activa.
        self._second.unload()
        self._first.unload()
        self.selected_device = None
        self.fallback_used = False
        self.fallback_reason = ""
        self._warmed = False
