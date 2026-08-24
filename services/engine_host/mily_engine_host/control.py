"""JSON-lines control plane for Engine Host lifecycle and diagnostics."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TextIO

from .host import AdapterHealth, EngineHost, EngineHostError, EngineHostSnapshot

ENGINE_HOST_VERSION = "1.0.0"


def _error(
    request_id: str | None,
    code: str,
    message: str,
    *,
    adapter_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "requestId": request_id,
        "ok": False,
        "errorCode": code,
        "errorMessage": message,
    }
    if adapter_id is not None:
        payload["adapterId"] = adapter_id
    return payload


def _health_payload(health: AdapterHealth) -> dict[str, object]:
    return {
        "adapterId": health.adapter_id,
        "status": health.status.value,
        "loaded": health.loaded,
        "failures": health.failures,
        "lastError": health.last_error,
    }


def _snapshot_payload(snapshot: EngineHostSnapshot) -> dict[str, object]:
    return {
        "version": ENGINE_HOST_VERSION,
        "loadedAdapters": snapshot.loaded_adapters,
        "maxLoadedAdapters": snapshot.max_loaded_adapters,
        "adapters": [_health_payload(item) for item in snapshot.adapters],
    }


def _adapter_id(request: Mapping[str, object], request_id: str) -> str | dict[str, object]:
    adapter_id = request.get("adapterId")
    if not isinstance(adapter_id, str) or not adapter_id.strip():
        return _error(
            request_id,
            "CONTROL_ADAPTER_REQUIRED",
            "adapterId es obligatorio para esta operación",
        )
    return adapter_id.strip()


def handle_request(host: EngineHost, request: object) -> dict[str, object]:
    if not isinstance(request, Mapping):
        return _error(None, "CONTROL_REQUEST", "El request JSON debe ser un objeto")

    request_id = request.get("requestId")
    if not isinstance(request_id, str) or not request_id.strip():
        return _error(None, "CONTROL_REQUEST_ID", "requestId es obligatorio")
    request_id = request_id.strip()

    operation = request.get("operation")
    if not isinstance(operation, str) or not operation.strip():
        return _error(request_id, "CONTROL_OPERATION", "operation es obligatoria")
    operation = operation.strip()

    try:
        if operation == "ping":
            return {
                "requestId": request_id,
                "ok": True,
                "operation": operation,
                "result": {"version": ENGINE_HOST_VERSION},
            }

        if operation == "discover":
            adapters = [
                {
                    "id": descriptor.id,
                    "kind": descriptor.kind.value,
                    "title": descriptor.title,
                    "version": descriptor.version,
                    "contract": descriptor.contract,
                }
                for descriptor in host.descriptors()
            ]
            return {
                "requestId": request_id,
                "ok": True,
                "operation": operation,
                "result": {"adapters": adapters},
            }

        if operation == "snapshot":
            return {
                "requestId": request_id,
                "ok": True,
                "operation": operation,
                "result": _snapshot_payload(host.snapshot(refresh_health=True)),
            }

        if operation == "load":
            adapter_id = _adapter_id(request, request_id)
            if isinstance(adapter_id, dict):
                return adapter_id
            config = request.get("config", {})
            if not isinstance(config, Mapping):
                return _error(
                    request_id,
                    "CONTROL_CONFIG",
                    "config debe ser un objeto JSON",
                    adapter_id=adapter_id,
                )
            health = host.load(adapter_id, dict(config))
            return {
                "requestId": request_id,
                "ok": True,
                "operation": operation,
                "result": _health_payload(health),
            }

        if operation == "unload":
            adapter_id = _adapter_id(request, request_id)
            if isinstance(adapter_id, dict):
                return adapter_id
            health = host.unload(adapter_id)
            return {
                "requestId": request_id,
                "ok": True,
                "operation": operation,
                "result": _health_payload(health),
            }

        return _error(
            request_id,
            "CONTROL_OPERATION",
            f"Operación no soportada: {operation}",
        )
    except EngineHostError as exc:
        return _error(
            request_id,
            exc.code,
            exc.message,
            adapter_id=exc.adapter_id,
        )
    except Exception as exc:
        # Control-plane failures are contained per request. The stream loop keeps
        # serving subsequent lines instead of terminating the host process.
        return _error(request_id, "CONTROL_INTERNAL", str(exc))


def serve_stream(host: EngineHost, source: TextIO, output: TextIO) -> None:
    for raw_line in source:
        line = raw_line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = _error(None, "CONTROL_JSON", f"JSON inválido: {exc.msg}")
        else:
            response = handle_request(host, request)
        output.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
        output.write("\n")
        output.flush()
