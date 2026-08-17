"""Protocolo WebSocket versionado entre extensión y motor local."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = 1
ALLOWED_SOURCES = {"auto", "en", "zh"}


class ProtocolError(ValueError):
    """Error de entrada que puede devolverse sin exponer detalles internos."""


@dataclass(slots=True)
class ClientMessage:
    """Mensaje normalizado recibido desde la extensión Chromium."""

    type: str
    protocol: int = PROTOCOL_VERSION
    source_language: str = "auto"
    target_language: str = "es"
    audio_base64: str | None = None
    sample_rate: int = 16000
    persist_transcript: bool = False

    @classmethod
    def parse(cls, raw: str) -> "ClientMessage":
        """Valida JSON y limita explícitamente las formas aceptadas."""
        try:
            payload: dict[str, Any] = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ProtocolError("JSON inválido") from exc

        protocol = int(payload.get("protocol", -1))
        if protocol != PROTOCOL_VERSION:
            raise ProtocolError("Versión de protocolo no compatible")

        message_type = str(payload.get("type", ""))
        if message_type not in {"client.hello", "audio.chunk", "audio.stop", "ping"}:
            raise ProtocolError("Tipo de mensaje no permitido")

        source = str(payload.get("sourceLanguage", "auto"))
        if source not in ALLOWED_SOURCES:
            raise ProtocolError("Idioma de origen no permitido")

        target = str(payload.get("targetLanguage", "es"))
        if target != "es":
            raise ProtocolError("Esta versión solo admite español como destino")

        audio_base64 = payload.get("audioBase64")
        if message_type == "audio.chunk" and not isinstance(audio_base64, str):
            raise ProtocolError("audio.chunk requiere audioBase64")

        sample_rate = int(payload.get("sampleRate", 16000))
        if sample_rate != 16000:
            raise ProtocolError("El audio debe enviarse a 16 kHz")

        return cls(
            type=message_type,
            protocol=protocol,
            source_language=source,
            target_language=target,
            audio_base64=audio_base64,
            sample_rate=sample_rate,
            persist_transcript=bool(payload.get("persistTranscript", False)),
        )


def event(event_type: str, **fields: Any) -> dict[str, Any]:
    """Construye eventos salientes con versión de protocolo siempre presente."""
    return {"protocol": PROTOCOL_VERSION, "type": event_type, **fields}
