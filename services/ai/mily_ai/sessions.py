"""Persistencia local opcional de transcripciones y exportación TXT/SRT."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class TranscriptSegment:
    start: float
    end: float
    original: str
    translation: str


@dataclass(slots=True)
class SessionResult:
    session_id: str
    metadata_path: Path | None
    txt_path: Path | None
    srt_path: Path | None


def _srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, rem = divmod(milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


class SessionRecorder:
    """Mantiene texto en memoria y solo persiste cuando el usuario lo habilita."""

    def __init__(self, sessions_dir: Path, persist_transcripts: bool = False):
        self.sessions_dir = Path(sessions_dir)
        self.persist_transcripts = persist_transcripts
        self.session_id = ""
        self.source_language = "auto"
        self.target_language = "es"
        self.started_at = 0.0
        self.segments: list[TranscriptSegment] = []

    def start(self, source_language: str, target_language: str) -> str:
        self.session_id = uuid.uuid4().hex
        self.source_language = source_language
        self.target_language = target_language
        self.started_at = time.monotonic()
        self.segments = []
        return self.session_id

    def add(self, segment: TranscriptSegment) -> None:
        self.segments.append(segment)

    def finish(self) -> SessionResult:
        session_id = self.session_id or uuid.uuid4().hex
        if not self.persist_transcripts:
            return SessionResult(session_id, None, None, None)

        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        folder = self.sessions_dir / session_id
        folder.mkdir(parents=True, exist_ok=False)
        duration = max((segment.end for segment in self.segments), default=0.0)
        metadata = {
            "schemaVersion": 1,
            "id": session_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "sourceLanguage": self.source_language,
            "targetLanguage": self.target_language,
            "durationSeconds": round(duration, 3),
            "segmentCount": len(self.segments),
        }
        metadata_path = folder / "session.json"
        txt_path = folder / "translation.txt"
        srt_path = folder / "translation.srt"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        txt_path.write_text("\n".join(s.translation for s in self.segments if s.translation).strip() + "\n", encoding="utf-8")
        blocks = []
        for index, segment in enumerate(self.segments, 1):
            blocks.append(
                f"{index}\n{_srt_timestamp(segment.start)} --> {_srt_timestamp(segment.end)}\n{segment.translation}\n"
            )
        srt_path.write_text("\n".join(blocks), encoding="utf-8")
        return SessionResult(session_id, metadata_path, txt_path, srt_path)
