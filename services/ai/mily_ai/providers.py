"""Proveedores intercambiables de ASR y traducción, cargados bajo demanda."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


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


class FasterWhisperAsr(AsrProvider):
    """Whisper vía CTranslate2; CPU int8 por defecto, CUDA float16 opcional."""

    def __init__(self, model_path: Path, compute_profile: str = "auto"):
        self.model_path = Path(model_path)
        self.compute_profile = compute_profile
        self._model = None

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
        self._model = WhisperModel(str(self.model_path), device=device, compute_type=compute_type, local_files_only=True)
        return self._model

    def transcribe(self, samples: Sequence[float], source_language: str) -> list[AsrSegment]:
        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("numpy no está instalado") from exc
        model = self._load()
        language = None if source_language == "auto" else source_language
        segments, info = model.transcribe(
            np.asarray(samples, dtype=np.float32),
            language=language,
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
            word_timestamps=False,
        )
        detected = getattr(info, "language", None) or source_language or "auto"
        return [
            AsrSegment(float(segment.start), float(segment.end), segment.text.strip(), detected)
            for segment in segments
            if segment.text.strip()
        ]


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
            generated = self._model.generate(**inputs, forced_bos_token_id=target_id, max_new_tokens=256, num_beams=1)
        return self._tokenizer.batch_decode(generated, skip_special_tokens=True)[0].strip()


class QwenTranslator(Translator):
    """Traductor causal Apache-2.0 para el pack comercial opcional."""

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
            raise RuntimeError("transformers/torch no están instalados") from exc
        use_cuda = self.compute_profile in {"auto", "gpu"} and torch.cuda.is_available()
        if self.compute_profile == "gpu" and not use_cuda:
            raise RuntimeError("Se solicitó GPU pero Torch CUDA no está disponible")
        self._device = "cuda" if use_cuda else "cpu"
        dtype = torch.float16 if use_cuda else torch.float32
        self._tokenizer = AutoTokenizer.from_pretrained(str(self.model_path), local_files_only=True)
        self._model = AutoModelForCausalLM.from_pretrained(str(self.model_path), local_files_only=True, torch_dtype=dtype)
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
        inputs = self._tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024).to(self._device)
        with torch.inference_mode():
            output = self._model.generate(**inputs, max_new_tokens=256, do_sample=False)
        new_tokens = output[0][inputs["input_ids"].shape[1] :]
        return self._tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
