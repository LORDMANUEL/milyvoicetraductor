"""Resolución de rutas de sesión para selección automática de packs."""

from __future__ import annotations


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
