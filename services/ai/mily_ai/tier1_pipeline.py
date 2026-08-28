"""Pipeline Tier 1 con destino de traducción explícito por sesión.

Mantiene `RealtimePipeline` como base estable y sustituye únicamente el
traductor para las rutas bidireccionales de 2.1.
"""

from __future__ import annotations

import json

from .pipeline import RealtimePipeline
from .provider_factory import build_translation_provider
from .providers import CachedTranslator, Translator
from .tier1_routes import (
    definition_for_installed_pack,
    mark_route_failure,
    route_supported_by_definition,
)

_TIER1_LANGUAGES = {"es", "en", "zh"}


def resolve_target_language(recorder, explicit: str | None) -> str:
    """Resuelve el destino de sesión sin depender del protocolo HTTP/WS."""

    candidate = str(explicit or getattr(recorder, "target_language", "es") or "es").strip().lower()
    return candidate if candidate in _TIER1_LANGUAGES else "es"


class ModelRouteUnsupported(RuntimeError):
    pass


class Tier1RealtimePipeline(RealtimePipeline):
    """Extensión mínima del pipeline base para ES↔EN/ZH."""

    def __init__(
        self,
        pack,
        source_language: str,
        compute_profile: str,
        recorder,
        *,
        target_language: str | None = None,
        session_mode: str = "meeting",
        speaker_detection: bool = False,
        speaker_focus_mode: str = "all",
        fixed_speaker_id: str | None = None,
    ):
        self.target_language = resolve_target_language(recorder, target_language)
        definition = definition_for_installed_pack(pack)
        if not route_supported_by_definition(
            definition, source_language, self.target_language
        ):
            mark_route_failure()
            raise ModelRouteUnsupported(
                f"Pack {getattr(pack, 'id', '')!s} no admite {source_language}-{self.target_language}"
            )

        super().__init__(
            pack,
            source_language,
            compute_profile,
            recorder,
            session_mode=session_mode,
            speaker_detection=speaker_detection,
            speaker_focus_mode=speaker_focus_mode,
            fixed_speaker_id=fixed_speaker_id,
        )

        metadata = json.loads((pack.path / "pack.json").read_text(encoding="utf-8"))
        component = metadata["components"]["translation"]

        # El proveedor creado por la base todavía no ha cargado pesos: se libera
        # de forma determinista y se sustituye por el traductor de esta ruta.
        self.translator.unload()
        translator: Translator = build_translation_provider(
            component,
            pack.path / "components" / "translation",
            compute_profile,
            self.cpu_budget,
            target_language=self.target_language,
        )
        self._translator_provider = translator
        self.translator = CachedTranslator(translator)

    @staticmethod
    def _detect_language(text: str, detected: str, configured: str) -> str:
        detected = str(detected or "").strip().lower()
        configured = str(configured or "").strip().lower()
        if detected in _TIER1_LANGUAGES:
            return detected
        if configured in _TIER1_LANGUAGES:
            return configured
        return "zh" if any("\u4e00" <= char <= "\u9fff" for char in text) else "en"
