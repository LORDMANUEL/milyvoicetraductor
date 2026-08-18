"""Políticas de backpressure para el pipeline realtime."""

from __future__ import annotations

import asyncio

from .pipeline import TranslationRequest


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
