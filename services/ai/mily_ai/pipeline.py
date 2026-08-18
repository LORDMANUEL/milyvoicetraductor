"""Pipeline de audio → ASR → traducción optimizado para subtítulos en tiempo real."""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass
from typing import Literal

from .cpu_budget import detect_cpu_budget
from .hypothesis import HypothesisStabilizer
from .models import InstalledPack
from .providers import (
    CachedTranslator,
    FasterWhisperAsr,
    M2M100CTranslate2Translator,
    NllbTranslator,
    QwenTranslator,
    Translator,
)
from .sessions import SessionRecorder, TranscriptSegment
from .streaming import AdaptiveSpeechSegmenter, AudioLevel, StreamingEvent


@dataclass(frozen=True, slots=True)
class PipelineEvent:
    """Evento semántico listo para salir por WebSocket."""

    type: Literal[
        "transcription.partial",
        "transcription.final",
        "translation.partial",
        "translation.final",
    ]
    start: float
    end: float
    original: str
    language: str
    translation: str = ""


@dataclass(frozen=True, slots=True)
class TranslationRequest:
    """Trabajo de traducción desacoplado del worker ASR."""

    type: Literal["translation.partial", "translation.final"]
    start: float
    end: float
    original: str
    language: str

    @property
    def final(self) -> bool:
        return self.type == "translation.final"


class RealtimePipeline:
    def __init__(self, pack: InstalledPack, source_language: str, compute_profile: str, recorder: SessionRecorder):
        metadata = __import__("json").loads((pack.path / "pack.json").read_text(encoding="utf-8"))
        components = metadata["components"]
        self.source_language = source_language
        self.sample_rate = 16000
        self.segmenter = AdaptiveSpeechSegmenter(sample_rate=self.sample_rate)
        self.stabilizer = HypothesisStabilizer()
        self.recorder = recorder
        self._recent_originals: deque[str] = deque(maxlen=8)
        self._last_partial_translation = ""

        cpu_profile = os.environ.get("MILY_CPU_PROFILE", "balanced")
        self.cpu_budget = detect_cpu_budget(cpu_profile)
        self.asr = FasterWhisperAsr(
            pack.path / "components" / "asr",
            compute_profile,
            cpu_budget=self.cpu_budget,
        )
        provider = components["translation"]["provider"]
        translation_path = pack.path / "components" / "translation"
        translator: Translator
        if provider == "m2m100-ct2":
            translator = M2M100CTranslate2Translator(
                translation_path,
                compute_profile,
                cpu_budget=self.cpu_budget,
            )
        elif provider == "qwen":
            translator = QwenTranslator(translation_path, compute_profile)
        else:
            translator = NllbTranslator(translation_path, compute_profile)
        self.translator = CachedTranslator(translator)

    @property
    def audio_level(self) -> AudioLevel:
        return self.segmenter.level

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.split())

    @staticmethod
    def _detect_language(text: str, detected: str, configured: str) -> str:
        if detected in {"en", "zh"}:
            return detected
        if configured in {"en", "zh"}:
            return configured
        return "zh" if any("\u4e00" <= char <= "\u9fff" for char in text) else "en"

    def ingest(self, samples) -> tuple[list[PipelineEvent], list[TranslationRequest]]:
        """Ejecuta únicamente segmentación + ASR; nunca llama al traductor."""

        events: list[PipelineEvent] = []
        requests: list[TranslationRequest] = []
        for window in self.segmenter.push(samples):
            window_events, window_requests = self._ingest_window(window)
            events.extend(window_events)
            requests.extend(window_requests)
        return events, requests

    def flush_ingest(self) -> tuple[list[PipelineEvent], list[TranslationRequest]]:
        """Finaliza audio pendiente sin bloquearse esperando traducción."""

        events: list[PipelineEvent] = []
        requests: list[TranslationRequest] = []
        for window in self.segmenter.flush():
            window_events, window_requests = self._ingest_window(window)
            events.extend(window_events)
            requests.extend(window_requests)
        return events, requests

    def execute_translation(self, request: TranslationRequest) -> PipelineEvent:
        """Ejecuta un trabajo M2M100 y persiste únicamente frases finales."""

        translated = self.translator.translate(request.original, request.language)
        if request.final:
            self.recorder.add(
                TranscriptSegment(
                    start=request.start,
                    end=request.end,
                    original=request.original,
                    translation=translated,
                )
            )
        return PipelineEvent(
            type=request.type,
            start=request.start,
            end=request.end,
            original=request.original,
            language=request.language,
            translation=translated,
        )

    def push(self, samples) -> list[PipelineEvent]:
        """Ruta síncrona de compatibilidad y pruebas."""

        events, requests = self.ingest(samples)
        events.extend(self.execute_translation(request) for request in requests)
        return events

    def flush(self) -> list[PipelineEvent]:
        """Ruta síncrona de compatibilidad y pruebas."""

        events, requests = self.flush_ingest()
        events.extend(self.execute_translation(request) for request in requests)
        return events

    def _transcribe_window(self, window: StreamingEvent) -> tuple[str, str]:
        segments = self.asr.transcribe(window.samples, self.source_language)
        original = self._normalize(" ".join(segment.text for segment in segments if segment.text))
        detected = next(
            (segment.language for segment in segments if segment.language in {"en", "zh"}),
            self.source_language,
        )
        return original, self._detect_language(original, detected, self.source_language)

    def _ingest_window(
        self, window: StreamingEvent
    ) -> tuple[list[PipelineEvent], list[TranslationRequest]]:
        original, detected = self._transcribe_window(window)
        start = window.start_sample / self.sample_rate
        end = window.end_sample / self.sample_rate

        if window.kind == "partial":
            if not original:
                return [], []
            state = self.stabilizer.update(original)
            events = [
                PipelineEvent(
                    type="transcription.partial",
                    start=start,
                    end=end,
                    original=state.partial,
                    language=detected,
                )
            ]
            requests: list[TranslationRequest] = []
            if (
                state.stable_advanced
                and len(state.stable.split()) >= 2
                and state.stable.casefold() != self._last_partial_translation.casefold()
            ):
                self._last_partial_translation = state.stable
                requests.append(
                    TranslationRequest(
                        type="translation.partial",
                        start=start,
                        end=end,
                        original=state.stable,
                        language=detected,
                    )
                )
            return events, requests

        final_original = self.stabilizer.finalize(original)
        self._last_partial_translation = ""
        if not final_original:
            return [], []
        folded = final_original.casefold()
        if folded in self._recent_originals:
            return [], []
        self._recent_originals.append(folded)
        return [
            PipelineEvent(
                type="transcription.final",
                start=start,
                end=end,
                original=final_original,
                language=detected,
            )
        ], [
            TranslationRequest(
                type="translation.final",
                start=start,
                end=end,
                original=final_original,
                language=detected,
            )
        ]
