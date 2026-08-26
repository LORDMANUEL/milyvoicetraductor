"""Protocolo WebSocket versionado entre extensión y motor local."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .languages import get_tier1_route, normalize_language

PROTOCOL_VERSION = 1
ALLOWED_SESSION_MODES = {"meeting", "education", "karaoke", "compact"}
ALLOWED_SOURCE_MODES = {"browser_tab", "microphone", "media_file", "system_loopback"}
ALLOWED_SPEAKER_FOCUS = {"all", "dominant", "fixed"}
SPEAKER_ID = re.compile(r"^speaker-[a-z]$")


class ProtocolError(ValueError):
    """Error de entrada que puede devolverse sin exponer detalles internos."""


@dataclass(slots=True)
class ClientMessage:
    """Mensaje normalizado recibido desde la extensión Chromium/Desktop."""

    type: str
    protocol: int = PROTOCOL_VERSION
    source_language: str = "auto"
    target_language: str = "es"
    audio_base64: str | None = None
    sample_rate: int = 16000
    persist_transcript: bool = False
    binary_pcm: bool = False
    session_mode: str = "meeting"
    source_mode: str = "browser_tab"
    external_pcm: bool = False
    speaker_detection: bool = False
    speaker_focus_mode: str = "all"
    speaker_id: str | None = None
    tts_text: str | None = None

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
        if message_type not in {
            "client.hello",
            "audio.chunk",
            "audio.stop",
            "speaker.focus",
            "tts.started",
            "tts.finished",
            "ping",
        }:
            raise ProtocolError("Tipo de mensaje no permitido")

        source = normalize_language(str(payload.get("sourceLanguage", "auto")))
        target = normalize_language(str(payload.get("targetLanguage", "es")))
        if not (source == "auto" and target == "es") and get_tier1_route(source, target) is None:
            raise ProtocolError("Ruta de idioma no permitida")

        session_mode = str(payload.get("sessionMode", "meeting"))
        if session_mode not in ALLOWED_SESSION_MODES:
            raise ProtocolError("Modo de sesión no permitido")

        source_mode = str(payload.get("sourceMode", "browser_tab"))
        if source_mode not in ALLOWED_SOURCE_MODES:
            raise ProtocolError("Fuente de audio no permitida")

        speaker_focus_mode = str(payload.get("speakerFocusMode", "all"))
        if speaker_focus_mode not in ALLOWED_SPEAKER_FOCUS:
            raise ProtocolError("Modo de foco de hablante no permitido")

        raw_speaker_id = payload.get("speakerId")
        speaker_id = str(raw_speaker_id) if raw_speaker_id is not None else None
        if speaker_id is not None and not SPEAKER_ID.fullmatch(speaker_id):
            raise ProtocolError("Identificador de hablante no permitido")
        if message_type == "speaker.focus" and speaker_focus_mode == "fixed" and not speaker_id:
            raise ProtocolError("speaker.focus fixed requiere speakerId")

        tts_text: str | None = None
        if message_type == "tts.started":
            raw_text = payload.get("text")
            if not isinstance(raw_text, str) or not raw_text.strip():
                raise ProtocolError("tts.started requiere texto")
            tts_text = raw_text.strip()[:1200]

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
            binary_pcm=bool(payload.get("binaryPcm", False)),
            session_mode=session_mode,
            source_mode=source_mode,
            external_pcm=bool(payload.get("externalPcm", False)),
            speaker_detection=bool(payload.get("speakerDetection", False)),
            speaker_focus_mode=speaker_focus_mode,
            speaker_id=speaker_id,
            tts_text=tts_text,
        )


def event(event_type: str, **fields: Any) -> dict[str, Any]:
    """Construye eventos salientes con versión de protocolo siempre presente."""
    return {"protocol": PROTOCOL_VERSION, "type": event_type, **fields}
