"""Extensión 2.1 de la cascada Marian con warm-up por idioma real."""

from __future__ import annotations

from .marian_cascade import CTranslate2MarianCascadeTranslator

_WARMUP_TEXT = {
    "es": "Confirme la reunión de hoy y el número de pedido.",
    "en": "Please confirm today's meeting and the order number.",
    "zh": "请确认今天的会议和订单号码。",
}


def warmup_text(language: str) -> str:
    return _WARMUP_TEXT.get(str(language).strip().lower(), _WARMUP_TEXT["en"])


class Tier1MarianCascadeTranslator(CTranslate2MarianCascadeTranslator):
    """Cascada Marian bidireccional con precalentamiento coherente por etapa."""

    def warm_up(self) -> None:
        if self._warmed:
            return
        self._first.translate(
            warmup_text(self.source_language), self.source_language
        )
        self._second.translate(
            warmup_text(self.pivot_language), self.pivot_language
        )
        self._sync_status()
        self._warmed = True
