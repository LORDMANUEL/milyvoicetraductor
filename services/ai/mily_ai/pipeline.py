"""Pipeline de audio → ASR → traducción con deduplicación básica."""

from __future__ import annotations

from .audio import PcmChunkBuffer
from .models import InstalledPack
from .providers import FasterWhisperAsr, NllbTranslator, QwenTranslator
from .sessions import SessionRecorder, TranscriptSegment


class RealtimePipeline:
    def __init__(self, pack: InstalledPack, source_language: str, compute_profile: str, recorder: SessionRecorder):
        metadata = __import__("json").loads((pack.path / "pack.json").read_text(encoding="utf-8"))
        components = metadata["components"]
        self.source_language = source_language
        self.buffer = PcmChunkBuffer()
        self.recorder = recorder
        self.elapsed = 0.0
        self._last_original = ""
        self.asr = FasterWhisperAsr(pack.path / "components" / "asr", compute_profile)
        provider = components["translation"]["provider"]
        translation_path = pack.path / "components" / "translation"
        self.translator = QwenTranslator(translation_path, compute_profile) if provider == "qwen" else NllbTranslator(translation_path, compute_profile)

    def push(self, samples: list[float]) -> list[TranscriptSegment]:
        window = self.buffer.push_samples(samples)
        return self._process(window) if window else []

    def flush(self) -> list[TranscriptSegment]:
        window = self.buffer.flush()
        return self._process(window) if window else []

    def _process(self, samples: list[float]) -> list[TranscriptSegment]:
        segments = self.asr.transcribe(samples, self.source_language)
        output: list[TranscriptSegment] = []
        for segment in segments:
            original = segment.text.strip()
            if not original or original == self._last_original:
                continue
            detected = segment.language if segment.language in {"en", "zh"} else self.source_language
            if detected == "auto":
                detected = "zh" if any("\u4e00" <= char <= "\u9fff" for char in original) else "en"
            translated = self.translator.translate(original, detected)
            item = TranscriptSegment(
                start=self.elapsed + segment.start,
                end=self.elapsed + segment.end,
                original=original,
                translation=translated,
            )
            self.recorder.add(item)
            output.append(item)
            self._last_original = original
        self.elapsed += max((s.end for s in segments), default=len(samples) / 16000.0)
        return output
