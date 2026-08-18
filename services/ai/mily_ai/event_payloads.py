"""Serialización estable de eventos realtime hacia clientes locales."""

from __future__ import annotations

from typing import Any


def pipeline_event_fields(item: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "start": item.start,
        "end": item.end,
        "original": item.original,
        "language": item.language,
    }
    if item.translation:
        fields["translation"] = item.translation
    words = getattr(item, "words", ()) or ()
    if words:
        fields["words"] = [
            {"start": word.start, "end": word.end, "text": word.text}
            for word in words
        ]
    return fields
