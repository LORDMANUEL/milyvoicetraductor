"""Pipeline de audio → ASR → traducción optimizado para subtítulos en tiempo real."""

from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

from .cpu_budget import detect_cpu_budget
from .echo_guard import EchoGuard
from .hypothesis import HypothesisStabilizer
from .models import InstalledPack
from .providers import (
    AsrWord,
    CachedTranslator,
    FasterWhisperAsr,
    M2M100CTranslate2Translator,
    NllbTranslator,
    QwenTranslator,
    Translator,
)
from .sessions import SessionRecorder, TranscriptSegment, TranscriptWord
from .speakers import SpeakerClusterer
from .streaming import AdaptiveSpeechSegmenter, AudioLevel, StreamingEvent
from .telemetry import RealtimeTelemetry


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
    words: tuple[AsrWord, ...] = ()
    speaker_id: str | None = None


@dataclass(frozen=True, slots=True)
class TranslationRequest:
    """Trabajo de traducción desacoplado del worker ASR."""

    type: Literal["translation.partial", "translation.final"]
    start: float
    end: float
    original: str
    language: str
    words: tuple[AsrWord, ...] = ()
    speaker_id: str | None = None

    @property
    def final(self) -> bool:
        return self.type == "translation.final"


class RealtimePipeline:
    def __init__(
        self,
        pack: InstalledPack,
        source_language: str,
        compute_profile: str,
        recorder: SessionRecorder,
        session_mode: str = "meeting",
        speaker_detection: bool = False,
        speaker_focus_mode: str = "all",
        fixed_speaker_id: str | None = None,
    ):
        metadata = __import__("json").loads(
            (pack.path / "pack.json").read_text(encoding="utf-8")
        )
        components = metadata["components"]
        self.source_language = source_language
        self.session_mode = session_mode if session_mode in {
            "meeting", "education", "karaoke", "compact"
        } else "meeting"
        self.sample_rate = 16000
        if self.session_mode == "karaoke":
            self.segmenter = AdaptiveSpeechSegmenter(
                sample_rate=self.sample_rate,
                first_decode_ms=1200,
                partial_step_ms=650,
                finalize_silence_ms=450,
                max_utterance_ms=4000,
                energy_threshold=0.008,
            )
        else:
            self.segmenter = AdaptiveSpeechSegmenter(sample_rate=self.sample_rate)
        self.stabilizer = HypothesisStabilizer()
        self.telemetry = RealtimeTelemetry()
        self.recorder = recorder
        self.echo_guard = EchoGuard()
        self.speaker_clusterer = (
            SpeakerClusterer(sample_rate=self.sample_rate) if speaker_detection else None
        )
        self.speaker_focus_mode = (
            speaker_focus_mode if speaker_focus_mode in {"all", "dominant", "fixed"} else "all"
        )
        self.fixed_speaker_id = fixed_speaker_id
        self._recent_originals: deque[str] = deque(maxlen=8)
        self._last_partial_translation = ""

        cpu_profile = os.environ.get("MILY_CPU_PROFILE", "balanced")
        self.cpu_budget = detect_cpu_budget(cpu_profile)
        self.asr = FasterWhisperAsr(
            pack.path / "components" / "asr",
            compute_profile,
            cpu_budget=self.cpu_budget,
            word_timestamps=self.session_mode == "karaoke",
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
        self._translator_provider = translator
        self.translator = CachedTranslator(translator)

    @property
    def audio_level(self) -> AudioLevel:
        return self.segmenter.level

    @property
    def known_speakers(self) -> tuple[str, ...]:
        return self.speaker_clusterer.speaker_ids if self.speaker_clusterer else ()

    @property
    def compute_status(self) -> dict[str, str | bool]:
        """Expone únicamente el backend real y motivos de fallback ya sanitizados."""

        def provider_state(provider) -> tuple[str, bool, str]:
            device = str(getattr(provider, "selected_device", "") or "unknown").lower()
            if device not in {"cpu", "cuda", "directml", "openvino", "vulkan", "windowsml"}:
                device = "unknown"
            fallback = bool(getattr(provider, "fallback_used", False))
            reason = str(getattr(provider, "fallback_reason", "") or "")
            if len(reason) > 80:
                reason = reason[:80]
            return device, fallback, reason

        asr_device, asr_fallback, asr_reason = provider_state(self.asr)
        mt_device, mt_fallback, mt_reason = provider_state(self._translator_provider)
        return {
            "asrDevice": asr_device,
            "translationDevice": mt_device,
            "fallbackUsed": asr_fallback or mt_fallback,
            "asrFallbackUsed": asr_fallback,
            "translationFallbackUsed": mt_fallback,
            "asrFallbackReason": asr_reason,
            "translationFallbackReason": mt_reason,
        }

    def set_speaker_focus(self, mode: str, speaker_id: str | None = None) -> None:
        self.speaker_focus_mode = mode if mode in {"all", "dominant", "fixed"} else "all"
        self.fixed_speaker_id = speaker_id if self.speaker_focus_mode == "fixed" else None

    def register_tts(self, text: str) -> None:
        self.echo_guard.register(text)

    def warm_up_asr(self) -> None:
        warm_up = getattr(self.asr, "warm_up", None)
        if callable(warm_up):
            warm_up(self.source_language)

    def warm_up_translation(self) -> None:
        warm_up = getattr(self._translator_provider, "warm_up", None)
        if callable(warm_up):
            warm_up()

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

    def _speaker_for_window(self, window: StreamingEvent) -> str | None:
        clusterer = self.speaker_clusterer
        if clusterer is None:
            return None
        speaker_id = clusterer.assign(window.samples, update=window.kind == "final")
        if self.speaker_focus_mode == "fixed":
            if self.fixed_speaker_id and speaker_id != self.fixed_speaker_id:
                return ""
        elif self.speaker_focus_mode == "dominant":
            dominant = clusterer.dominant_id
            if dominant and speaker_id != dominant:
                return ""
        return speaker_id

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

        started = time.perf_counter()
        translated = self.translator.translate(request.original, request.language)
        self.telemetry.record_translation((time.perf_counter() - started) * 1000.0)
        if request.final:
            self.recorder.add(
                TranscriptSegment(
                    start=request.start,
                    end=request.end,
                    original=request.original,
                    translation=translated,
                    speaker_id=request.speaker_id,
                    words=tuple(
                        TranscriptWord(word.start, word.end, word.text)
                        for word in request.words
                    ),
                )
            )
        return PipelineEvent(
            type=request.type,
            start=request.start,
            end=request.end,
            original=request.original,
            language=request.language,
            translation=translated,
            words=request.words,
            speaker_id=request.speaker_id,
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

    def _transcribe_window(
        self, window: StreamingEvent
    ) -> tuple[str, str, tuple[AsrWord, ...]]:
        started = time.perf_counter()
        segments = self.asr.transcribe(window.samples, self.source_language)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self.telemetry.record_asr(
            elapsed_ms,
            audio_ms=len(window.samples) * 1000.0 / self.sample_rate,
        )
        original = self._normalize(
            " ".join(segment.text for segment in segments if segment.text)
        )
        detected = next(
            (
                segment.language
                for segment in segments
                if segment.language in {"en", "zh"}
            ),
            self.source_language,
        )
        offset = window.start_sample / self.sample_rate
        words = tuple(
            AsrWord(offset + word.start, offset + word.end, word.text)
            for segment in segments
            for word in segment.words
            if word.text
        )
        return (
            original,
            self._detect_language(original, detected, self.source_language),
            words,
        )

    def _ingest_window(
        self, window: StreamingEvent
    ) -> tuple[list[PipelineEvent], list[TranslationRequest]]:
        speaker_id = self._speaker_for_window(window)
        if speaker_id == "":
            return [], []

        original, detected, words = self._transcribe_window(window)
        if original and self.echo_guard.matches(original):
            return [], []
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
                    words=words,
                    speaker_id=speaker_id,
                )
            ]
            requests: list[TranslationRequest] = []
            if (
                state.stable_advanced
                and len(state.stable.split()) >= 2
                and state.stable.casefold()
                != self._last_partial_translation.casefold()
            ):
                self._last_partial_translation = state.stable
                requests.append(
                    TranslationRequest(
                        type="translation.partial",
                        start=start,
                        end=end,
                        original=state.stable,
                        language=detected,
                        words=words,
                        speaker_id=speaker_id,
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
                words=words,
                speaker_id=speaker_id,
            )
        ], [
            TranslationRequest(
                type="translation.final",
                start=start,
                end=end,
                original=final_original,
                language=detected,
                words=words,
                speaker_id=speaker_id,
            )
        ]
