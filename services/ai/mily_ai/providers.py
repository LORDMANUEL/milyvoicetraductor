"""Proveedores intercambiables de ASR y traducción, optimizados para tiempo real."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .cpu_budget import CpuBudget, detect_cpu_budget


@dataclass(slots=True)
class AsrSegment:
    start: float
    end: float
    text: str
    language: str


class AsrProvider(ABC):
    @abstractmethod
    def transcribe(self, samples: Sequence[float], source_language: str) -> list[AsrSegment]:
        raise NotImplementedError


class Translator(ABC):
    @abstractmethod
    def translate(self, text: str, source_language: str) -> str:
        raise NotImplementedError


class CachedTranslator(Translator):
    """LRU pequeño para no retraducir texto repetido por el solapamiento del ASR."""

    def __init__(self, inner: Translator, max_entries: int = 192):
        if max_entries <= 0:
            raise ValueError("max_entries debe ser positivo")
        self.inner = inner
        self.max_entries = max_entries
        self._cache: OrderedDict[tuple[str, str], str] = OrderedDict()

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.split())

    def translate(self, text: str, source_language: str) -> str:
        normalized = self._normalize(text)
        if not normalized:
            return ""
        key = (source_language, normalized)
        if key in self._cache:
            value = self._cache.pop(key)
            self._cache[key] = value
            return value
        value = self.inner.translate(normalized, source_language)
        self._cache[key] = value
        while len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)
        return value


class FasterWhisperAsr(AsrProvider):
    """Whisper vía CTranslate2; CPU INT8 y CUDA FP16 con lenguaje estabilizado."""

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget: CpuBudget | None = None,
    ):
        self.model_path = Path(model_path)
        self.compute_profile = compute_profile
        self.cpu_budget = cpu_budget or detect_cpu_budget()
        self._model = None
        self._locked_language: str | None = None
        self._warmed = False

    def _load(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("faster-whisper no está instalado") from exc

        device, compute_type = "cpu", "int8"
        if self.compute_profile in {"auto", "gpu"}:
            try:
                import ctranslate2

                if ctranslate2.get_cuda_device_count() > 0:
                    device, compute_type = "cuda", "float16"
                elif self.compute_profile == "gpu":
                    raise RuntimeError("Se solicitó GPU pero CUDA no está disponible")
            except ImportError:
                if self.compute_profile == "gpu":
                    raise RuntimeError("CTranslate2/CUDA no disponible")
        self._model = WhisperModel(
            str(self.model_path),
            device=device,
            compute_type=compute_type,
            cpu_threads=self.cpu_budget.asr_threads if device == "cpu" else 0,
            num_workers=1,
            local_files_only=True,
        )
        return self._model

    def warm_up(self, source_language: str = "en") -> None:
        """Carga pesos/kernels antes de recibir la primera frase del usuario."""

        if self._warmed:
            return
        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("numpy no está instalado") from exc
        model = self._load()
        language = source_language if source_language in {"en", "zh"} else "en"
        segments, _info = model.transcribe(
            np.zeros(16000, dtype=np.float32),
            language=language,
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
            word_timestamps=False,
            temperature=0.0,
        )
        # faster-whisper ejecuta la inferencia al consumir el generator.
        list(segments)
        self._warmed = True

    def transcribe(self, samples: Sequence[float], source_language: str) -> list[AsrSegment]:
        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("numpy no está instalado") from exc
        model = self._load()
        language = self._locked_language or (None if source_language == "auto" else source_language)
        segments, info = model.transcribe(
            np.asarray(samples, dtype=np.float32),
            language=language,
            beam_size=1,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300, "speech_pad_ms": 80},
            condition_on_previous_text=False,
            word_timestamps=False,
            temperature=0.0,
        )
        detected = getattr(info, "language", None) or language or source_language or "auto"
        probability = float(getattr(info, "language_probability", 0.0) or 0.0)
        if source_language == "auto" and detected in {"en", "zh"} and probability >= 0.78:
            self._locked_language = detected
        return [
            AsrSegment(float(segment.start), float(segment.end), segment.text.strip(), detected)
            for segment in segments
            if segment.text.strip()
        ]


class M2M100CTranslate2Translator(Translator):
    """M2M100 convertido una vez a CTranslate2 INT8 para traducción rápida local."""

    def __init__(
        self,
        model_path: Path,
        compute_profile: str = "auto",
        cpu_budget: CpuBudget | None = None,
    ):
        self.model_path = Path(model_path)
        self.compute_profile = compute_profile
        self.cpu_budget = cpu_budget or detect_cpu_budget()
        self._translator = None
        self._tokenizer = None
        self._warmed = False

    def _load(self):
        if self._translator is not None:
            return
        try:
            import ctranslate2
            from transformers import AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("CTranslate2/Transformers no están instalados") from exc

        device = "cpu"
        compute_type = "int8"
        if self.compute_profile in {"auto", "gpu"}:
            if ctranslate2.get_cuda_device_count() > 0:
                device, compute_type = "cuda", "auto"
            elif self.compute_profile == "gpu":
                raise RuntimeError("Se solicitó GPU pero CUDA no está disponible")
        self._translator = ctranslate2.Translator(
            str(self.model_path),
            device=device,
            compute_type=compute_type,
            inter_threads=1,
            intra_threads=self.cpu_budget.translation_threads if device == "cpu" else 0,
        )
        tokenizer_path = self.model_path / "tokenizer"
        if not tokenizer_path.is_dir():
            tokenizer_path = self.model_path
        self._tokenizer = AutoTokenizer.from_pretrained(
            str(tokenizer_path), local_files_only=True
        )

    @staticmethod
    def _decoding_limit(source_tokens: int) -> int:
        """Acota la salida a una frase realtime sin reservar 192 pasos siempre."""

        return min(128, max(24, source_tokens * 2 + 12))

    def warm_up(self) -> None:
        """Carga tokenizer, pesos y kernels con una traducción mínima."""

        if self._warmed:
            return
        self.translate("Hello.", "en")
        self._warmed = True

    def translate(self, text: str, source_language: str) -> str:
        if not text.strip():
            return ""
        self._load()
        assert self._translator is not None and self._tokenizer is not None
        source_language = "zh" if source_language == "zh" else "en"
        self._tokenizer.src_lang = source_language
        source = self._tokenizer.convert_ids_to_tokens(self._tokenizer.encode(text))
        target_prefix = [self._tokenizer.lang_code_to_token["es"]]
        results = self._translator.translate_batch(
            [source],
            target_prefix=[target_prefix],
            beam_size=1,
            return_scores=False,
            max_decoding_length=self._decoding_limit(len(source)),
        )
        target = results[0].hypotheses[0][1:]
        token_ids = self._tokenizer.convert_tokens_to_ids(target)
        return self._tokenizer.decode(token_ids, skip_special_tokens=True).strip()


class NllbTranslator(Translator):
    """NLLB local. Pack marcado como no comercial por la licencia del modelo."""

    LANG_CODES = {"en": "eng_Latn", "zh": "zho_Hans", "auto": "eng_Latn"}

    def __init__(self, model_path: Path, compute_profile: str = "auto"):
        self.model_path = Path(model_path)
        self.compute_profile = compute_profile
        self._tokenizer = None
        self._model = None
        self._device = "cpu"

    def _load(self):
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("transformers/torch no están instalados") from exc
        use_cuda = self.compute_profile in {"auto", "gpu"} and torch.cuda.is_available()
        if self.compute_profile == "gpu" and not use_cuda:
            raise RuntimeError("Se solicitó GPU pero Torch CUDA no está disponible")
        self._device = "cuda" if use_cuda else "cpu"
        self._tokenizer = AutoTokenizer.from_pretrained(str(self.model_path), local_files_only=True)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(str(self.model_path), local_files_only=True)
        self._model.to(self._device)
        self._model.eval()

    def translate(self, text: str, source_language: str) -> str:
        if not text.strip():
            return ""
        self._load()
        import torch

        assert self._tokenizer is not None and self._model is not None
        source_code = self.LANG_CODES.get(source_language, "eng_Latn")
        self._tokenizer.src_lang = source_code
        inputs = self._tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(self._device)
        target_id = self._tokenizer.convert_tokens_to_ids("spa_Latn")
        with torch.inference_mode():
            generated = self._model.generate(
                **inputs,
                forced_bos_token_id=target_id,
                max_new_tokens=192,
                num_beams=1,
            )
        return self._tokenizer.batch_decode(generated, skip_special_tokens=True)[0].strip()


class QwenTranslator(Translator):
    """Traductor causal Apache-2.0; se conserva como perfil de contexto/calidad."""

    def __init__(self, model_path: Path, compute_profile: str = "auto"):
        self.model_path = Path(model_path)
        self.compute_profile = compute_profile
        self._tokenizer = None
        self._model = None
        self._device = "cpu"

    def _load(self):
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("transformers/torch no están instalado") from exc
        use_cuda = self.compute_profile in {"auto", "gpu"} and torch.cuda.is_available()
        if self.compute_profile == "gpu" and not use_cuda:
            raise RuntimeError("Se solicitó GPU pero Torch CUDA no está disponible")
        self._device = "cuda" if use_cuda else "cpu"
        dtype = torch.float16 if use_cuda else torch.float32
        self._tokenizer = AutoTokenizer.from_pretrained(str(self.model_path), local_files_only=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            str(self.model_path), local_files_only=True, torch_dtype=dtype
        )
        self._model.to(self._device)
        self._model.eval()

    def translate(self, text: str, source_language: str) -> str:
        if not text.strip():
            return ""
        self._load()
        import torch

        assert self._tokenizer is not None and self._model is not None
        source_label = "chino" if source_language == "zh" else "inglés"
        instruction = (
            "Eres un intérprete profesional. Traduce fielmente de " + source_label + " a español. "
            "Conserva nombres propios, números y términos técnicos. Devuelve únicamente la traducción."
        )
        messages = [
            {"role": "system", "content": instruction},
            {"role": "user", "content": text},
        ]
        try:
            prompt = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
            )
        except (AttributeError, TypeError):
            prompt = instruction + "\n\n" + text
        inputs = self._tokenizer(prompt, return_tensors="pt", truncation=True, max_length=768).to(self._device)
        max_new_tokens = min(160, max(48, int(inputs["input_ids"].shape[1] * 1.6)))
        with torch.inference_mode():
            output = self._model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        new_tokens = output[0][inputs["input_ids"].shape[1] :]
        return self._tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
