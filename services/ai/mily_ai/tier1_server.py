"""Integración Tier 1 sobre el servidor estable sin duplicar su hot path."""

from __future__ import annotations

from . import __version__
from . import server as base_server
from .tier1_model_operations import download_pack as tier1_download_pack
from .tier1_pipeline import Tier1RealtimePipeline
from .tier1_routes import consume_route_failure, route_supported_by_definition


def _install_tier1_hooks() -> None:
    """Instala hooks idempotentes sobre los puntos de extensión del servidor."""

    base_server.RealtimePipeline = Tier1RealtimePipeline
    base_server.download_pack = tier1_download_pack
    if getattr(base_server, "_mily_tier1_event_hook", False):
        return

    original_event = base_server.event

    def tier1_event(event_type: str, **fields):
        if event_type == "engine.ready":
            fields["version"] = __version__
        elif (
            event_type == "engine.error"
            and fields.get("code") == "PIPELINE_INIT"
            and consume_route_failure()
        ):
            fields["code"] = "MODEL_ROUTE_UNSUPPORTED"
            fields["message"] = (
                "El modelo activo no admite esta ruta. "
                "Selecciona u optimiza un modelo compatible."
            )
        return original_event(event_type, **fields)

    base_server.event = tier1_event
    base_server._mily_tier1_event_hook = True


def _patch_health_version(app) -> None:
    """Actualiza la respuesta health sin reimplementar el endpoint estable."""

    for route in getattr(app, "routes", []):
        if getattr(route, "path", None) != "/health":
            continue
        original = getattr(route, "endpoint", None)
        if original is None or getattr(original, "_mily_tier1_health", False):
            continue

        async def health_with_tier1_version(_original=original):
            payload = await _original()
            if isinstance(payload, dict):
                payload = dict(payload)
                payload["version"] = __version__
            return payload

        health_with_tier1_version._mily_tier1_health = True
        route.endpoint = health_with_tier1_version
        dependant = getattr(route, "dependant", None)
        if dependant is not None:
            dependant.call = health_with_tier1_version
        break


def create_app(paths, port: int = 8765, parent_pid: int | None = None):
    _install_tier1_hooks()
    app = base_server.create_app(paths, port, parent_pid)
    _patch_health_version(app)
    return app


__all__ = ["create_app", "route_supported_by_definition"]
