"""Conversión Marian/OPUS nativa para el runtime BetaAlpha Lite.

BetaAlpha excluye Torch/Transformers del runtime de inferencia. Este módulo usa
los pesos Marian originales y OpusMTConverter de CTranslate2 para producir el
mismo formato CT2 INT8 sin cargar frameworks de entrenamiento.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


_TINY_EN_ES_REPO = "Helsinki-NLP/opus-mt_tiny_eng-spa"
_TINY_MODEL = "final.model.npz.best-perplexity.npz"
_TINY_DECODER = "final.model.npz.best-perplexity.npz.decoder.yml"
_TINY_VOCAB = "vocab.spm"

_ZH_EN_REPO = "Helsinki-NLP/opus-mt-zh-en"
_ZH_EN_OPUS_URL = (
    "https://object.pouta.csc.fi/Tatoeba-MT-models/zho-eng/opus-2020-07-17.zip"
)


def _download_hf_file(component: dict[str, Any], filename: str, target: Path) -> Path:
    from huggingface_hub import hf_hub_download

    cached = Path(
        hf_hub_download(
            repo_id=str(component["repoId"]),
            revision=str(component.get("revision", "main")),
            filename=filename,
        )
    )
    destination = target / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cached, destination)
    return destination


def _prepare_tiny_native_source(component: dict[str, Any], target: Path) -> Path:
    for filename in (_TINY_MODEL, _TINY_DECODER, _TINY_VOCAB):
        if not (target / filename).is_file():
            _download_hf_file(component, filename, target)
    shutil.copy2(target / _TINY_DECODER, target / "decoder.yml")
    return target


def _safe_extract_zip(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if not members or len(members) > 128:
            raise RuntimeError("archivo OPUS inválido")
        total = 0
        root = destination.resolve()
        for member in members:
            if member.is_dir():
                continue
            size = int(member.file_size)
            if size < 0 or size > 2 * 1024 * 1024 * 1024:
                raise RuntimeError("archivo OPUS fuera de límites")
            total += size
            if total > 3 * 1024 * 1024 * 1024:
                raise RuntimeError("archivo OPUS demasiado grande")
            out = (destination / member.filename).resolve()
            if root != out and root not in out.parents:
                raise RuntimeError("ruta insegura dentro de OPUS")
        bundle.extractall(destination)


def _download_zh_en_native_source(target: Path) -> Path:
    native = target / ".opus-native"
    shutil.rmtree(native, ignore_errors=True)
    native.mkdir(parents=True, exist_ok=True)
    archive = native / "opus-2020-07-17.zip"
    request = urllib.request.Request(
        _ZH_EN_OPUS_URL,
        headers={"User-Agent": "MilyVoiceTraductor-BetaAlpha/2.0.1"},
    )
    with urllib.request.urlopen(request, timeout=90) as response, archive.open("wb") as output:
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > 1_500_000_000:
            raise RuntimeError("archivo OPUS excede el límite de descarga")
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > 1_500_000_000:
                raise RuntimeError("archivo OPUS excede el límite de descarga")
            digest.update(chunk)
            output.write(chunk)
    if total < 1024:
        raise RuntimeError("descarga OPUS incompleta")
    (native / "source.sha256").write_text(digest.hexdigest(), encoding="ascii")
    extracted = native / "source"
    extracted.mkdir(parents=True, exist_ok=True)
    _safe_extract_zip(archive, extracted)
    candidates = [extracted] + [path for path in extracted.rglob("*") if path.is_dir()]
    for candidate in candidates:
        if (candidate / "decoder.yml").is_file():
            return candidate
    raise RuntimeError("el archivo OPUS no contiene decoder.yml")


def _convert_native_opus(
    component: dict[str, Any], target: Path, quantization: str
) -> None:
    from . import models

    if models._is_marian_ready(target):
        return
    try:
        import ctranslate2
    except ImportError as exc:
        raise models.ModelOperationError(
            "MODEL_RUNTIME_ERROR",
            "El runtime Lite no contiene CTranslate2.",
        ) from exc

    repo_id = str(component.get("repoId", ""))
    output = target.with_name(target.name + ".ct2")
    shutil.rmtree(output, ignore_errors=True)
    try:
        if repo_id == _TINY_EN_ES_REPO:
            native_source = _prepare_tiny_native_source(component, target)
        elif repo_id == _ZH_EN_REPO:
            native_source = _download_zh_en_native_source(target)
        else:
            raise models.ModelOperationError(
                "MODEL_NATIVE_SOURCE_UNAVAILABLE",
                "Este modelo Marian no tiene una fuente nativa aprobada para BetaAlpha Lite.",
            )
        converter = ctranslate2.converters.OpusMTConverter(str(native_source))
        converter.convert(str(output), quantization=quantization, force=True)
        if not models._is_ctranslate2_model(output):
            raise RuntimeError("OpusMTConverter no produjo model.bin/config.json")
        models._copy_marian_tokenizer(target, output)
        if not models._is_marian_ready(output):
            raise RuntimeError("el modelo OPUS convertido no contiene tokenizer utilizable")
        shutil.rmtree(target)
        output.replace(target)
    except models.ModelOperationError:
        shutil.rmtree(output, ignore_errors=True)
        raise
    except BaseException as exc:
        shutil.rmtree(output, ignore_errors=True)
        raise models.ModelOperationError(
            "MODEL_CONVERSION_ERROR",
            "El modelo Marian no pudo convertirse con el conversor OPUS ligero.",
        ) from exc


def install_betaalpha_native_marian_patch() -> None:
    """Instala el preparador Lite antes de importar CLI/model_operations."""

    from . import models

    if getattr(models, "_betaalpha_native_marian_installed", False):
        return
    original_prepare = models._prepare_component

    def prepare(component: dict[str, Any], target: Path) -> None:
        provider = str(component.get("provider", ""))
        if provider == "marian-ct2":
            _convert_native_opus(
                component,
                Path(target),
                str(component.get("quantization", "int8")),
            )
            return
        original_prepare(component, target)

    models._prepare_component = prepare
    models._betaalpha_native_marian_installed = True
