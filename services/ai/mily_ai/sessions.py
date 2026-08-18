"""Persistencia local opcional y exportación bilingüe de transcripciones."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TranscriptWord:
    start: float
    end: float
    text: str


@dataclass(slots=True)
class TranscriptSegment:
    start: float
    end: float
    original: str
    translation: str
    speaker_id: str | None = None
    words: tuple[TranscriptWord, ...] = ()


@dataclass(slots=True)
class SessionResult:
    session_id: str
    metadata_path: Path | None
    txt_path: Path | None
    srt_path: Path | None
    srt_bilingual_path: Path | None
    vtt_path: Path | None


def _srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, rem = divmod(milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _vtt_timestamp(seconds: float) -> str:
    return _srt_timestamp(seconds).replace(",", ".")


def _speaker_label(speaker_id: str | None) -> str:
    if not speaker_id:
        return ""
    suffix = speaker_id.removeprefix("speaker-").strip()
    if len(suffix) == 1 and suffix.isalpha():
        return f"Hablante {suffix.upper()}"
    return f"Hablante {suffix or speaker_id}"


def _word_timed_original(segment: TranscriptSegment) -> str:
    if not segment.words:
        return segment.original
    return " ".join(
        f"<{_vtt_timestamp(word.start)}>{word.text.strip()}"
        for word in segment.words
        if word.text.strip()
    ) or segment.original


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
            return SessionResult(session_id, None, None, None, None, None)

        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        folder = self.sessions_dir / session_id
        folder.mkdir(parents=True, exist_ok=False)
        duration = max((segment.end for segment in self.segments), default=0.0)
        speakers = sorted(
            {segment.speaker_id for segment in self.segments if segment.speaker_id}
        )
        metadata = {
            "schemaVersion": 2,
            "id": session_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "sourceLanguage": self.source_language,
            "targetLanguage": self.target_language,
            "durationSeconds": round(duration, 3),
            "segmentCount": len(self.segments),
            "speakerCount": len(speakers),
            "hasWordTimestamps": any(segment.words for segment in self.segments),
        }
        metadata_path = folder / "session.json"
        txt_path = folder / "translation.txt"
        srt_path = folder / "translation.srt"
        srt_bilingual_path = folder / "translation-bilingual.srt"
        vtt_path = folder / "translation.vtt"
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        txt_blocks: list[str] = []
        spanish_srt: list[str] = []
        bilingual_srt: list[str] = []
        vtt_blocks: list[str] = ["WEBVTT", ""]
        for index, segment in enumerate(self.segments, 1):
            label = _speaker_label(segment.speaker_id)
            header = f"[{label}]\n" if label else ""
            txt_blocks.append(
                f"{header}{segment.original}\n{segment.translation}".strip()
            )
            span = (
                f"{_srt_timestamp(segment.start)} --> "
                f"{_srt_timestamp(segment.end)}"
            )
            spanish_srt.append(f"{index}\n{span}\n{segment.translation}\n")
            bilingual_lines = [
                line for line in (label, segment.translation, segment.original) if line
            ]
            bilingual_srt.append(
                f"{index}\n{span}\n" + "\n".join(bilingual_lines) + "\n"
            )
            vtt_span = (
                f"{_vtt_timestamp(segment.start)} --> "
                f"{_vtt_timestamp(segment.end)}"
            )
            vtt_lines = [
                line
                for line in (label, segment.translation, _word_timed_original(segment))
                if line
            ]
            vtt_blocks.extend([vtt_span, "\n".join(vtt_lines), ""])

        txt_path.write_text(
            "\n\n".join(txt_blocks).strip() + "\n", encoding="utf-8"
        )
        srt_path.write_text("\n".join(spanish_srt), encoding="utf-8")
        srt_bilingual_path.write_text(
            "\n".join(bilingual_srt), encoding="utf-8"
        )
        vtt_path.write_text("\n".join(vtt_blocks), encoding="utf-8")
        return SessionResult(
            session_id,
            metadata_path,
            txt_path,
            srt_path,
            srt_bilingual_path,
            vtt_path,
        )
