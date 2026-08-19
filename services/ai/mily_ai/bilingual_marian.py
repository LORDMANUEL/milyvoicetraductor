"""Router Marian bilingüe EN/ZH→ES para BetaAlpha.

Comparte EN→ES entre la ruta inglesa y la segunda etapa de ZH→EN→ES, por lo que
el modo automático no necesita cargar un tercer traductor.
"""

from __future__ import annotations

from pathlib import Path

from .cpu_budget import CpuBudget
from .marian_realtime import CTranslate2RealtimeMarianTranslator
from .optional_providers import OptionalProviderRuntimeError
from .providers import Translator


class CTranslate2BilingualMarianRouter(Translator):
    """EN→ES directo y ZH→EN→ES con dos modelos Marian residentes."""

    def __init__(
        self,
        model_path: Path,
        compute_profile: str,
        cpu_budget: CpuBudget,
        *,
        target_language: str = "es",
        auto_tune_compute_type: bool = False,
    ):
        self.model_path = Path(model_path)
        self.source_languages = {"en", "zh"}
        self.target_language = target_language
        self._zh_en = CTranslate2RealtimeMarianTranslator(
            self.model_path / "stage-1",
            compute_profile,
            cpu_budget=cpu_budget,
            source_language="zh",
            target_language="en",
            auto_tune_compute_type=auto_tune_compute_type,
        )
        self._en_es = CTranslate2RealtimeMarianTranslator(
            self.model_path / "stage-2",
            compute_profile,
            cpu_budget=cpu_budget,
            source_language="en",
            target_language=target_language,
            auto_tune_compute_type=auto_tune_compute_type,
        )
        self.selected_device: str | None = None
        self.fallback_used = False
        self.fallback_reason = ""
        self._warmed = False

    @staticmethod
    def _detect(text: str) -> str:
        return "zh" if any("\u4e00" <= char <= "\u9fff" for char in text) else "en"

    def _sync_status(self) -> None:
        devices = {
            str(getattr(stage, "selected_device", "") or "unknown").lower()
            for stage in (self._zh_en, self._en_es)
        }
        self.selected_device = devices.pop() if len(devices) == 1 else "cpu"
        self.fallback_used = any(
            bool(getattr(stage, "fallback_used", False))
            for stage in (self._zh_en, self._en_es)
        )
        reasons = [
            str(getattr(stage, "fallback_reason", "") or "").strip()
            for stage in (self._zh_en, self._en_es)
        ]
        self.fallback_reason = "; ".join(reason for reason in reasons if reason)[:80]

    def translate(self, text: str, source_language: str) -> str:
        if not text.strip():
            return ""
        language = str(source_language or "auto").strip().lower()
        if language == "auto":
            language = self._detect(text)
        if language not in self.source_languages:
            raise OptionalProviderRuntimeError(
                "MARIAN_BILINGUAL_ROUTE_MISMATCH",
                "El router BetaAlpha solo admite inglés o mandarín hacia español.",
            )
        if language == "en":
            translated = self._en_es.translate(text, "en")
        else:
            pivot = self._zh_en.translate(text, "zh")
            translated = self._en_es.translate(pivot, "en") if pivot.strip() else ""
        self._sync_status()
        return translated

    def warm_up(self) -> None:
        if self._warmed:
            return
        # Calienta ambos caminos para que el primer cambio de idioma no pague carga.
        self._en_es.translate("Hello.", "en")
        self._zh_en.translate("你好。", "zh")
        self._sync_status()
        self._warmed = True

    @property
    def selected_compute_types(self) -> tuple[str | None, str | None]:
        return (
            self._zh_en.selected_compute_type,
            self._en_es.selected_compute_type,
        )

    def unload(self) -> None:
        self._en_es.unload()
        self._zh_en.unload()
        self.selected_device = None
        self.fallback_used = False
        self.fallback_reason = ""
        self._warmed = False
