"""Adapters opcionales del Engine Hub.

Los constructores son baratos y no importan runtimes pesados. El runtime/modelo
solo se abre cuando MilyCompute selecciona el adapter y llega la primera carga.
"""

from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any, Sequence

from .compute_router import load_backend_with_fallback
from .cpu_budget import CpuBudget, detect_cpu_budget
from .providers import AsrProvider, AsrSegment, Translator


class OptionalProviderRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class CTranslate2MarianTranslator(Translator):
    """OPUS/Marian directo sobre CTranslate2 INT8 y SentencePiece."""

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget: CpuBudget | None = None,
        *,
        source_language: str = "en",
        target_language: str = "es",
    ):
        self.model_path = Path(model_path)
        self.compute_profile = compute_profile
        self.cpu_budget = cpu_budget or detect_cpu_budget()
        self.source_language = source_language
        self.target_language = target_language
        self._translator = None
        self._source_sp = None
        self._target_sp = None
        self._warmed = False
        self.selected_device: str | None = None
        self.fallback_used = False
        self.fallback_reason = ""

    def _sentencepiece_file(self, names: tuple[str, ...]) -> Path:
        for name in names:
            direct = self.model_path / name
            if direct.is_file():
                return direct
            nested = self.model_path / "tokenizer" / name
            if nested.is_file():
                return nested
        raise OptionalProviderRuntimeError(
            "MARIAN_TOKENIZER_MISSING",
            "El pack Marian no contiene sus tokenizadores SentencePiece.",
        )

    def _load(self) -> None:
        if self._translator is not None:
            return
        try:
            import ctranslate2
            import sentencepiece as spm
        except ImportError as exc:
            raise OptionalProviderRuntimeError(
                "MARIAN_RUNTIME_MISSING",
                "El runtime local no contiene CTranslate2/SentencePiece para OPUS-MT.",
            ) from exc

        cuda_count = (
            int(ctranslate2.get_cuda_device_count())
            if self.compute_profile in {"auto", "gpu"}
            else 0
        )

        def loader(device: str):
            return ctranslate2.Translator(
                str(self.model_path),
                device=device,
                compute_type="auto" if device == "cuda" else "int8",
                inter_threads=1,
                intra_threads=(
                    self.cpu_budget.translation_threads if device == "cpu" else 0
                ),
            )

        result = load_backend_with_fallback(self.compute_profile, cuda_count, loader)
        self._translator = result.value
        self.selected_device = result.device
        self.fallback_used = result.fallback_used
        self.fallback_reason = result.reason
        source_path = self._sentencepiece_file(
            ("source.spm", "source.model", "sentencepiece.source.model")
        )
        target_path = self._sentencepiece_file(
            ("target.spm", "target.model", "sentencepiece.target.model")
        )
        self._source_sp = spm.SentencePieceProcessor(model_file=str(source_path))
        self._target_sp = spm.SentencePieceProcessor(model_file=str(target_path))

    @staticmethod
    def _decoding_limit(source_tokens: int) -> int:
        return min(96, max(16, source_tokens * 2 + 8))

    def translate(self, text: str, source_language: str) -> str:
        if not text.strip():
            return ""
        if source_language not in {self.source_language, "auto"}:
            raise OptionalProviderRuntimeError(
                "MARIAN_ROUTE_MISMATCH",
                "El modelo directo no admite esta dirección de traducción.",
            )
        self._load()
        assert self._translator is not None
        assert self._source_sp is not None and self._target_sp is not None
        source_tokens = self._source_sp.encode(text.strip(), out_type=str)
        result = self._translator.translate_batch(
            [source_tokens],
            beam_size=1,
            return_scores=False,
            max_decoding_length=self._decoding_limit(len(source_tokens)),
        )[0]
        return self._target_sp.decode(result.hypotheses[0]).strip()

    def warm_up(self) -> None:
        if not self._warmed:
            self.translate("Hello.", self.source_language)
            self._warmed = True

    def unload(self) -> None:
        translator = self._translator
        if translator is not None:
            unload = getattr(translator, "unload_model", None)
            if callable(unload):
                unload(to_cpu=False)
        self._translator = None
        self._source_sp = None
        self._target_sp = None
        self._warmed = False


class MoonshineAsr(AsrProvider):
    """Moonshine Voice para PCM suministrado por MilyVoice."""

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget: CpuBudget | None = None,
        word_timestamps: bool = False,
    ):
        self.model_path = Path(model_path)
        self.compute_profile = compute_profile
        self.cpu_budget = cpu_budget or detect_cpu_budget()
        self.word_timestamps = bool(word_timestamps)
        self._transcriber = None
        self.selected_device = "cpu"
        self.fallback_used = compute_profile == "gpu"
        self.fallback_reason = (
            "Moonshine usa su proveedor ONNX configurado; GPU forzada no se garantiza."
            if compute_profile == "gpu"
            else ""
        )

    def _load(self):
        if self._transcriber is not None:
            return self._transcriber
        try:
            from moonshine_voice import Transcriber
        except ImportError as exc:
            raise OptionalProviderRuntimeError(
                "MOONSHINE_RUNTIME_MISSING",
                "Moonshine Voice no está instalado en este runtime.",
            ) from exc
        try:
            self._transcriber = Transcriber(str(self.model_path))
        except Exception as exc:
            raise OptionalProviderRuntimeError(
                "MOONSHINE_MODEL_LOAD",
                "Moonshine no pudo abrir el modelo seleccionado.",
            ) from exc
        return self._transcriber

    @staticmethod
    def _text_from_result(result: Any) -> str:
        if isinstance(result, str):
            return result.strip()
        text = str(getattr(result, "text", "") or "").strip()
        if text:
            return text
        try:
            return " ".join(
                str(getattr(item, "text", item)).strip()
                for item in result
                if str(getattr(item, "text", item)).strip()
            ).strip()
        except TypeError:
            return ""

    def transcribe(
        self, samples: Sequence[float], source_language: str
    ) -> list[AsrSegment]:
        transcriber = self._load()
        result = transcriber.transcribe_without_streaming(
            [float(value) for value in samples], 16000
        )
        text = self._text_from_result(result)
        if not text:
            return []
        return [
            AsrSegment(
                start=0.0,
                end=len(samples) / 16000.0,
                text=text,
                language="en" if source_language == "auto" else source_language,
            )
        ]

    def unload(self) -> None:
        close = getattr(self._transcriber, "close", None)
        if callable(close):
            close()
        self._transcriber = None


class SherpaOnnxAsr(AsrProvider):
    """Adapter sherpa-onnx configurado por `sherpa-config.json` del pack."""

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget: CpuBudget | None = None,
        word_timestamps: bool = False,
    ):
        self.model_path = Path(model_path)
        self.compute_profile = compute_profile
        self.cpu_budget = cpu_budget or detect_cpu_budget()
        self.word_timestamps = bool(word_timestamps)
        self._recognizer = None
        self.selected_device = "cpu"
        self.fallback_used = False
        self.fallback_reason = ""

    def _path(self, value: str) -> str:
        path = (self.model_path / value).resolve()
        if self.model_path.resolve() not in path.parents and path != self.model_path.resolve():
            raise OptionalProviderRuntimeError(
                "SHERPA_CONFIG_INVALID", "La configuración sherpa sale del pack."
            )
        if not path.is_file():
            raise OptionalProviderRuntimeError(
                "SHERPA_MODEL_MISSING", "Falta un archivo del modelo sherpa-onnx."
            )
        return str(path)

    def _load(self):
        if self._recognizer is not None:
            return self._recognizer
        try:
            import sherpa_onnx
        except ImportError as exc:
            raise OptionalProviderRuntimeError(
                "SHERPA_RUNTIME_MISSING",
                "sherpa-onnx no está instalado en este runtime.",
            ) from exc
        config_path = self.model_path / "sherpa-config.json"
        if not config_path.is_file():
            raise OptionalProviderRuntimeError(
                "SHERPA_CONFIG_MISSING",
                "El pack sherpa-onnx no contiene sherpa-config.json.",
            )
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        kind = str(payload.get("kind", "transducer"))
        common = {
            "tokens": self._path(str(payload["tokens"])),
            "num_threads": max(1, self.cpu_budget.asr_threads),
            "sample_rate": int(payload.get("sampleRate", 16000)),
            "feature_dim": int(payload.get("featureDim", 80)),
            "decoding_method": str(payload.get("decodingMethod", "greedy_search")),
            "debug": False,
        }
        try:
            if kind == "paraformer":
                self._recognizer = sherpa_onnx.OfflineRecognizer.from_paraformer(
                    paraformer=self._path(str(payload["model"])), **common
                )
            elif kind == "whisper":
                self._recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
                    encoder=self._path(str(payload["encoder"])),
                    decoder=self._path(str(payload["decoder"])),
                    language=str(payload.get("language", "en")),
                    task="transcribe",
                    **common,
                )
            else:
                self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                    encoder=self._path(str(payload["encoder"])),
                    decoder=self._path(str(payload["decoder"])),
                    joiner=self._path(str(payload["joiner"])),
                    **common,
                )
        except OptionalProviderRuntimeError:
            raise
        except Exception as exc:
            raise OptionalProviderRuntimeError(
                "SHERPA_MODEL_LOAD",
                "sherpa-onnx no pudo abrir el modelo seleccionado.",
            ) from exc
        return self._recognizer

    def transcribe(
        self, samples: Sequence[float], source_language: str
    ) -> list[AsrSegment]:
        recognizer = self._load()
        stream = recognizer.create_stream()
        stream.accept_waveform(16000, [float(value) for value in samples])
        recognizer.decode_stream(stream)
        result = stream.result
        text = str(getattr(result, "text", "") or "").strip()
        if not text:
            return []
        return [
            AsrSegment(
                start=0.0,
                end=len(samples) / 16000.0,
                text=text,
                language="en" if source_language == "auto" else source_language,
            )
        ]

    def unload(self) -> None:
        self._recognizer = None


class WhisperCppAsr(AsrProvider):
    """whisper.cpp mediante sidecar nativo y modelo GGUF cuantizado."""

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget: CpuBudget | None = None,
        word_timestamps: bool = False,
    ):
        self.model_path = Path(model_path)
        self.compute_profile = compute_profile
        self.cpu_budget = cpu_budget or detect_cpu_budget()
        self.word_timestamps = bool(word_timestamps)
        self.selected_device = "vulkan" if compute_profile == "gpu" else "cpu"
        self.fallback_used = False
        self.fallback_reason = ""

    def _binary(self) -> Path:
        configured = os.environ.get("MILY_WHISPER_CPP", "").strip()
        candidates = [
            Path(configured) if configured else Path(),
            self.model_path / "whisper-cli.exe",
            self.model_path / "whisper-cli",
        ]
        for candidate in candidates:
            if str(candidate) and candidate.is_file():
                return candidate
        found = shutil.which("whisper-cli")
        if found:
            return Path(found)
        raise OptionalProviderRuntimeError(
            "WHISPER_CPP_RUNTIME_MISSING",
            "No se encontró el sidecar whisper.cpp autorizado.",
        )

    def _model(self) -> Path:
        models = sorted(self.model_path.glob("*.gguf")) + sorted(
            self.model_path.glob("ggml-*.bin")
        )
        if not models:
            raise OptionalProviderRuntimeError(
                "WHISPER_CPP_MODEL_MISSING",
                "El pack whisper.cpp no contiene un modelo cuantizado.",
            )
        return models[0]

    @staticmethod
    def _write_wave(path: Path, samples: Sequence[float]) -> None:
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            pcm = b"".join(
                struct.pack("<h", max(-32768, min(32767, round(float(v) * 32767))))
                for v in samples
            )
            handle.writeframes(pcm)

    def transcribe(
        self, samples: Sequence[float], source_language: str
    ) -> list[AsrSegment]:
        with tempfile.TemporaryDirectory(prefix="mily-whisper-cpp-") as temp:
            wav_path = Path(temp) / "input.wav"
            output_base = Path(temp) / "result"
            self._write_wave(wav_path, samples)
            command = [
                str(self._binary()),
                "-m",
                str(self._model()),
                "-f",
                str(wav_path),
                "-of",
                str(output_base),
                "-otxt",
                "-t",
                str(max(1, self.cpu_budget.asr_threads)),
                "-l",
                "en" if source_language == "auto" else source_language,
                "-np",
            ]
            try:
                subprocess.run(
                    command,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=30,
                    creationflags=(
                        getattr(subprocess, "CREATE_NO_WINDOW", 0)
                        if os.name == "nt"
                        else 0
                    ),
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise OptionalProviderRuntimeError(
                    "WHISPER_CPP_EXECUTION",
                    "whisper.cpp no pudo procesar el fragmento de audio.",
                ) from exc
            result_path = output_base.with_suffix(".txt")
            text = (
                result_path.read_text(encoding="utf-8", errors="replace").strip()
                if result_path.is_file()
                else ""
            )
        if not text:
            return []
        return [
            AsrSegment(
                start=0.0,
                end=len(samples) / 16000.0,
                text=text,
                language="en" if source_language == "auto" else source_language,
            )
        ]


class GoogleChirpAsr(AsrProvider):
    """Conector cloud explícito; nunca se activa sin credenciales/consentimiento."""

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget: CpuBudget | None = None,
        word_timestamps: bool = False,
    ):
        self.model_path = Path(model_path)
        self.compute_profile = compute_profile
        self.cpu_budget = cpu_budget or detect_cpu_budget()
        self.word_timestamps = bool(word_timestamps)
        self.selected_device = "cloud"
        self.fallback_used = False
        self.fallback_reason = ""

    def transcribe(
        self, samples: Sequence[float], source_language: str
    ) -> list[AsrSegment]:
        raise OptionalProviderRuntimeError(
            "GOOGLE_CHIRP_NOT_CONFIGURED",
            "Google Chirp requiere consentimiento, proyecto y credenciales cloud.",
        )
