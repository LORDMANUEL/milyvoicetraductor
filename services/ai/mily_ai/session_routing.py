"""Resolución de rutas de sesión para selección automática de packs."""

from __future__ import annotations

from copy import deepcopy


_BETAALPHA_AUTO_SPANISH_PACK = "betaalpha-paraformer-zh-es"


def automatic_spanish_pack_id() -> str:
    return _BETAALPHA_AUTO_SPANISH_PACK


def route_for_languages(source_language: str, target_language: str) -> str | None:
    source = str(source_language or "").strip().lower()
    target = str(target_language or "").strip().lower()
    if target != "es" or source not in {"en", "zh"}:
        return None
    return f"{source}-{target}"


def supports_route(definition: dict, route: str) -> bool:
    return str(route).lower() in {
        str(item).strip().lower() for item in definition.get("routes", ())
    }


def supports_automatic_spanish(definition: dict) -> bool:
    routes = {
        str(item).strip().lower() for item in definition.get("routes", ())
    }
    return {"en-es", "zh-es"}.issubset(routes)


def adapt_components_for_session(
    pack_id: str,
    components: dict,
    source_language: str,
    target_language: str,
) -> dict:
    """Vuelve bilingüe el Paraformer existente solo durante una sesión Auto.

    Los metadatos firmados del pack permanecen inmutables. La traducción reutiliza
    las mismas carpetas stage-1 (ZH→EN) y stage-2 (EN→ES); inglés salta stage-1.
    """

    output = deepcopy(components)
    if (
        str(pack_id) != _BETAALPHA_AUTO_SPANISH_PACK
        or str(source_language).lower() != "auto"
        or str(target_language).lower() != "es"
    ):
        return output
    asr = output.get("asr")
    translation = output.get("translation")
    if isinstance(asr, dict):
        asr["language"] = "auto"
    if isinstance(translation, dict):
        translation["provider"] = "marian-bilingual-router-ct2"
        translation["betaAlphaTuneComputeType"] = True
    return output
