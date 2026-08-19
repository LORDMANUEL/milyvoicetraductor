"""Pipeline de audio → ASR → traducción optimizado para subtítulos en tiempo real."""

from __future__ import annotations

import os
import time
from collections import deque
from dataclasses import dataclass
from typing import Literal

from .betaalpha_optimization import (
    AdaptiveStreamingController,
    IncrementalTranslationPlanner,
)
from .cpu_budget import detect_cpu_budget
from .echo_guard import EchoGuard
from .hypothesis import HypothesisStabilizer
from .models import InstalledPack
from .provider_factory import build_asr_provider, build_translation_provider
from .providers import AsrWord, CachedTranslator, Translator
from .sessions import SessionRecorder, TranscriptSegment, TranscriptWord
from .speakers import SpeakerClusterer
from .streaming import AdaptiveSpeechSegmenter, AudioLevel, StreamingEvent
from .telemetry import RealtimeTelemetry


@dataclass(frozen=True, slots=True)
class PipelineEvent:
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
    type: Literal["translation.partial", "translation.final"]
    start: float
    end: float
    original: str
    language: str
    words: tuple[AsrWord, ...] = ()
    speaker_id: str | None = None
    utterance_id: str = ""
    created_at: float = 0.0

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
        self.session_mode = (
            session_mode
            if session_mode in {"meeting", "education", "karaoke", "compact"}
            else "meeting"
        )
        self.sample_rate = 16000
        self._betaalpha_mode = str(pack.id).startswith("betaalpha-")
        self._betaalpha_streaming = (
            AdaptiveStreamingController() if self._betaalpha_mode else None
        )
        self._betaalpha_translation = (
            IncrementalTranslationPlanner() if self._betaalpha_mode else None
        )

        if self.session_mode == "karaoke":
            self.segmenter = AdaptiveSpeechSegmenter(
                sample_rate=self.sample_rate,
                first_decode_ms=1200,
                partial_step_ms=650,
                finalize_silence_ms=450,
                max_utterance_ms=4000,
                energy_threshold=0.008,
            )
        elif self._betaalpha_mode:
            self.segmenter = AdaptiveSpeechSegmenter(
                sample_rate=self.sample_rate,
                partial_step_ms=450,
            )
        else:
            self.segmenter = AdaptiveSpeechSegmenter(sample_rate=self.sample_rate)

        self.stabilizer = HypothesisStabilizer()
        self.telemetry = RealtimeTelemetry()
        self.recorder = recorder
        self.echo_guard = EchoGuard()
        self._speaker_detection_requested = bool(speaker_detection)
        self._word_timestamps_requested = self.session_mode == "karaoke"
        self._resource_mode = "healthy"
        self.speaker_clusterer = (
            SpeakerClusterer(sample_rate=self.sample_rate) if speaker_detection else None
        )
        self.speaker_focus_mode = (
            speaker_focus_mode
            if speaker_focus_mode in {"all", "dominant", "fixed"}
            else "all"
        )
        self.fixed_speaker_id = fixed_speaker_id
        self._recent_originals: deque[str] = deque(maxlen=8)
        self._last_partial_translation = ""

        cpu_profile = os.environ.get("MILY_CPU_PROFILE", "balanced")
        self.cpu_budget = detect_cpu_budget(cpu_profile)
        self.asr = build_asr_provider(
            components["asr"],
            pack.path / "components" / "asr",
            compute_profile,
            self.cpu_budget,
            self._word_timestamps_requested,
        )
        translator: Translator = build_translation_provider(
            components["translation"],
            pack.path / "components" / "translation",
            compute_profile,
            self.cpu_budget,
        )
        self._translator_provider = translator
        self.translator = CachedTranslator(translator)

    @property
    def audio_level(self) -> AudioLevel:
        return self.segmenter.level

    @property
    def resource_mode(self) -> str:
        return self._resource_mode

    @property
    def speaker_detection_enabled(self) -> bool:
        return self._speaker_detection_requested and self._resource_mode == "healthy"

    @property
    def known_speakers(self) -> tuple[str, ...]:
        if not self.speaker_detection_enabled:
            return ()
        return self.speaker_clusterer.speaker_ids if self.speaker_clusterer else ()

    @property
    def compute_status(self) -> dict[str, str | bool]:
        def provider_state(provider) -> tuple[str, bool, str]:
            device = str(getattr(provider, "selected_device", "") or "unknown").lower()
            if device not in {
                "cpu",
                "cuda",
                "directml",
                "openvino",
                "vulkan",
                "windowsml",
                "cloud",
            }:
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
            "resourceMode": self._resource_mode,
        }

    def _update_betaalpha_partial_cadence(self) -> None:
        controller = self._betaalpha_streaming
        if controller is None or self.session_mode == "karaoke":
            return
        snapshot = self.telemetry.snapshot(
            audio_queue_ms=0,
            translation_queue_depth=0,
        )
        interval = controller.interval_ms(
            rtf_p95=snapshot.real_time_factor_p95,
            pressure=self._resource_mode != "healthy",
        )
        self.segmenter.set_partial_step_ms(interval)

    def set_resource_mode(self, mode: str) -> None:
        normalized = str(mode).strip().lower()
        if normalized not in {"healthy", "pressure", "catch_up", "rescue"}:
            normalized = "rescue"
        self._resource_mode = normalized
        if hasattr(self.asr, "word_timestamps"):
            self.asr.word_timestamps = bool(
                self._word_timestamps_requested and normalized == "healthy"
            )
        if self._betaalpha_mode:
            self.segmenter.set_partial_decoding(normalized in {"healthy", "pressure"})
            self._update_betaalpha_partial_cadence()

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

    def unload(self) -> None:
        if self._betaalpha_translation is not None:
            self._betaalpha_translation.reset()
        for provider in (self.asr, self.translator):
            unload = getattr(provider, "unload", None)
            if callable(unload):
                unload()

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

    @staticmethod
    def _utterance_id(window: StreamingEvent) -> str:
        return f"u-{window.start_sample}"

    def _speaker_for_window(self, window: StreamingEvent) -> str | None:
        if not self.speaker_detection_enabled:
            return None
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
        events: list[PipelineEvent] = []
        requests: list[TranslationRequest] = []
        for window in self.segmenter.push(samples):
            window_events, window_requests = self._ingest_window(window)
            events.extend(window_events)
            requests.extend(window_requests)
        return events, requests

    def flush_ingest(self) -> tuple[list[PipelineEvent], list[TranslationRequest]]:
        events: list[PipelineEvent] = []
        requests: list[TranslationRequest] = []
        for window in self.segmenter.flush():
            window_events, window_requests = self._ingest_window(window)
            events.extend(window_events)
            requests.extend(window_requests)
        return events, requests

    def _translate_request_text(self, request: TranslationRequest) -> str:
        planner = self._betaalpha_translation
        if planner is None or request.final:
            translated = self.translator.translate(request.original, request.language)
            if planner is not None:
                planner.reset()
            return translated

        plan = planner.plan(request.original, request.language)
        if not plan.text_to_translate:
            return plan.stable_translation_prefix
        tail = self.translator.translate(plan.text_to_translate, request.language)
        translated = " ".join(
            part for part in (plan.stable_translation_prefix, tail) if part
        ).strip()
        planner.commit(plan, tail)
        return translated

    def execute_translation(self, request: TranslationRequest) -> PipelineEvent:
        started = time.perf_counter()
        translated = self._translate_request_text(request)
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
        events, requests = self.ingest(samples)
        events.extend(self.execute_translation(request) for request in requests)
        return events

    def flush(self) -> list[PipelineEvent]:
        events, requests = self.flush_ingest()
        events.extend(self.execute_translation(request) for request in requests)
        return events

    def _transcribe_window(
        self, window: StreamingEvent
    ) -> tuple[str, str, tuple[AsrWord, ...]]:
        started = time.perf_counter()
        final_transcribe = getattr(self.asr, "transcribe_final", None)
        if window.kind == "final" and callable(final_transcribe):
            segments = final_transcribe(window.samples, self.source_language)
        else:
            segments = self.asr.transcribe(window.samples, self.source_language)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        self.telemetry.record_asr(
            elapsed_ms,
            audio_ms=len(window.samples) * 1000.0 / self.sample_rate,
        )
        if self._betaalpha_mode:
            self._update_betaalpha_partial_cadence()
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
        if window.kind == "final" and not hasattr(self.asr, "transcribe_final"):
            finish_utterance = getattr(self.asr, "finish_utterance", None)
            if callable(finish_utterance):
                finish_utterance()
        if original and self.echo_guard.matches(original):
            return [], []
        start = window.start_sample / self.sample_rate
        end = window.end_sample / self.sample_rate
        utterance_id = self._utterance_id(window)
        created_at = time.monotonic()

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
                        utterance_id=utterance_id,
                        created_at=created_at,
                    )
                )
            return events, requests

        final_original = self.stabilizer.finalize(original)
        self._last_partial_translation = ""
        if not final_original:
            if self._betaalpha_translation is not None:
                self._betaalpha_translation.reset()
            return [], []
        folded = final_original.casefold()
        if folded in self._recent_originals:
            if self._betaalpha_translation is not None:
                self._betaalpha_translation.reset()
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
                utterance_id=utterance_id,
                created_at=created_at,
            )
        ]
