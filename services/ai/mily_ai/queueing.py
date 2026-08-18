"""Políticas de backpressure para el pipeline realtime."""

from __future__ import annotations

import asyncio
from typing import Literal

from .pipeline import TranslationRequest

SerialTranslationAction = Literal["run", "defer", "drop"]


def serial_translation_action(
    request: TranslationRequest, *, audio_pending: bool
) -> SerialTranslationAction:
    """Prioriza ASR cuando CPU débil comparte un único executor.

    En modo serial una traducción y Whisper compiten por el mismo worker. Un
    parcial queda obsoleto rápidamente y se descarta si ya existe audio esperando.
    Una frase final nunca se pierde: únicamente se difiere brevemente. Cuando la
    cola de audio está vacía, cualquier traducción puede ejecutarse inmediatamente.
    """

    if not audio_pending:
        return "run"
    return "defer" if request.final else "drop"


async def enqueue_translation(
    queue: asyncio.Queue[TranslationRequest], request: TranslationRequest
) -> bool:
    """Encola traducciones sin sacrificar nunca una frase final.

    Los parciales son información de baja prioridad y pueden quedar obsoletos antes
    de ser procesados. Si la cola está llena, se descartan. Los finales representan
    una utterance cerrada: esperan capacidad y siempre se conservan.
    """

    if request.final:
        await queue.put(request)
        return True
    try:
        queue.put_nowait(request)
        return True
    except asyncio.QueueFull:
        return False
