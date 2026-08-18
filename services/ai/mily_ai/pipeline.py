"""Pipeline de audio → ASR → traducción optimizado para subtítulos en tiempo real."""

from __future__ import annotations

from collections import deque

from .audio import PcmChunkBuffer
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


class RealtimePipeline:
    def __init__(self, pack: InstalledPack, source_language: str, compute_profile: str, recorder: SessionRecorder):
        metadata = __import__("json").loads((pack.path / "pack.json").read_text(encoding="utf-8"))
        components = metadata["components"]
        self.source_language = source_language
        # Dos segundos conservan suficiente contexto para Whisper y reducen ~17 %
        # la espera frente al buffer anterior de 2.4 s. El VAD interno puede cortar
        # silencios antes de decodificar contenido inútil.
        self.buffer = PcmChunkBuffer(window_seconds=2.0, overlap_seconds=0.25)
        self.recorder = recorder
        self.elapsed = 0.0
        self._recent_originals: deque[str] = deque(maxlen=6)
        self.asr = FasterWhisperAsr(pack.path / "components" / "asr", compute_profile)
        provider = components["translation"]["provider"]
        translation_path = pack.path / "components" / "translation"
        translator: Translator
        if provider == "m2m100-ct2":
            translator = M2M100CTranslate2Translator(translation_path, compute_profile)
        elif provider == "qwen":
            translator = QwenTranslator(translation_path, compute_profile)
        else:
            translator = NllbTranslator(translation_path, compute_profile)
        self.translator = CachedTranslator(translator)

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.split())

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
            original = self._normalize(segment.text)
            if not original:
                continue
            # Whisper vuelve a ver 250 ms de contexto. Evitamos reemitir segmentos
            # idénticos recientes sin descartar frases nuevas que extienden la anterior.
            if original.casefold() in self._recent_originals:
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
            self._recent_originals.append(original.casefold())
        self.elapsed += max((s.end for s in segments), default=len(samples) / 16000.0)
        return output
