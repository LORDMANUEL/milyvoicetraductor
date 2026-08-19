"""Cascada Marian CT2 para rutas Lite sin modelo directo promovido.

La cascada mantiene dos modelos pequeños residentes para priorizar latencia. Ambos
se descargan/validan como datos y se liberan explícitamente al cambiar de pack.
BetaAlpha puede autoajustar el compute type de cada etapa por CPU.
"""

from __future__ import annotations

from pathlib import Path

from .cpu_budget import CpuBudget
from .marian_realtime import CTranslate2RealtimeMarianTranslator
from .optional_providers import OptionalProviderRuntimeError
from .providers import Translator


class CTranslate2MarianCascadeTranslator(Translator):
    """ZH→EN→ES sobre dos traductores Marian CTranslate2 pequeños."""

    def __init__(
        self,
        model_path: Path,
        compute_profile: str,
        cpu_budget: CpuBudget,
        *,
        source_language: str = "zh",
        pivot_language: str = "en",
        target_language: str = "es",
        auto_tune_compute_type: bool = False,
    ):
        self.model_path = Path(model_path)
        self.source_language = source_language
        self.pivot_language = pivot_language
        self.target_language = target_language
        self.auto_tune_compute_type = bool(auto_tune_compute_type)
        self._first = CTranslate2RealtimeMarianTranslator(
            self.model_path / "stage-1",
            compute_profile,
            cpu_budget=cpu_budget,
            source_language=source_language,
            target_language=pivot_language,
            auto_tune_compute_type=self.auto_tune_compute_type,
        )
        self._second = CTranslate2RealtimeMarianTranslator(
            self.model_path / "stage-2",
            compute_profile,
            cpu_budget=cpu_budget,
            source_language=pivot_language,
            target_language=target_language,
            auto_tune_compute_type=self.auto_tune_compute_type,
        )
        self.selected_device: str | None = None
        self.fallback_used = False
        self.fallback_reason = ""
        self._warmed = False

    @property
    def selected_compute_types(self) -> tuple[str | None, str | None]:
        return (
            self._first.selected_compute_type,
            self._second.selected_compute_type,
        )

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
        self.translate("你好。", self.source_language)
        self._warmed = True

    def unload(self) -> None:
        self._second.unload()
        self._first.unload()
        self.selected_device = None
        self.fallback_used = False
        self.fallback_reason = ""
        self._warmed = False
