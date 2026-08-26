"""Contrato runtime de rutas Tier 1 y señal de rechazo por sesión."""

from __future__ import annotations

import json
from contextvars import ContextVar
from pathlib import Path
from typing import Any

_ROUTE_FAILURE: ContextVar[bool] = ContextVar("mily_tier1_route_failure", default=False)


def route_supported_by_definition(definition: dict[str, Any], source: str, target: str) -> bool:
    routes = {
        str(route).strip().lower()
        for route in definition.get("routes", [])
        if str(route).strip()
    }
    source = str(source or "auto").strip().lower()
    target = str(target or "es").strip().lower()
    if source == "auto":
        return target == "es" and bool(routes.intersection({"en-es", "zh-es"}))
    return f"{source}-{target}" in routes


def definition_for_installed_pack(pack) -> dict[str, Any]:
    """Recupera la definición efectiva de un pack integrado o externo."""

    metadata_path = Path(pack.path) / "pack.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    embedded = metadata.get("definition")
    if isinstance(embedded, dict):
        return embedded

    pack_id = str(getattr(pack, "id", None) or metadata.get("id", ""))
    catalog_path = Path(__file__).with_name("model-packs.json")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    for definition in catalog.get("packs", []):
        if isinstance(definition, dict) and str(definition.get("id", "")) == pack_id:
            return definition
    return {"id": pack_id, "routes": []}


def mark_route_failure() -> None:
    _ROUTE_FAILURE.set(True)


def consume_route_failure() -> bool:
    failed = bool(_ROUTE_FAILURE.get())
    _ROUTE_FAILURE.set(False)
    return failed
