"""Operaciones de modelo que separan descarga en disco de activación en memoria."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from .models import (
    HuggingFacePackInstaller,
    InstalledPack,
    ModelCatalog,
    ModelOperationError,
    _file_manifest,
    _prepare_component,
)

_FAST_MOONSHINE_PACK = "fast-moonshine-en-es"
_LITE_ZH_ES_PACK = "lite-zh-es"

# Layout entregado por moonshine-voice 0.1.0 para ModelArch.TINY_STREAMING.
# Mantenerlo explícito evita aceptar descargas parciales y, a la vez, impide
# volver a validar nombres de una arquitectura antigua que el runtime actual no
# puede abrir.
_MOONSHINE_010_STREAMING_ASSETS = (
    "adapter.ort",
    "cross_kv.ort",
    "decoder_kv.ort",
    "encoder.ort",
    "frontend.ort",
    "streaming_config.json",
    "tokenizer.bin",
    "spelling_cnn.ort",
    "spelling_cnn_meta.json",
)


def _moonshine_streaming_model_ready(path: Path) -> bool:
    """Exige el layout streaming completo y archivos no vacíos."""

    root = Path(path)
    for name in _MOONSHINE_010_STREAMING_ASSETS:
        asset = root / name
        try:
            if not asset.is_file() or asset.stat().st_size <= 0:
                return False
        except OSError:
            return False
    return True


def _restore_state(catalog: ModelCatalog, state: dict[str, Any]) -> None:
    catalog.models_dir.mkdir(parents=True, exist_ok=True)
    temp = catalog.state_path.with_suffix(".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(catalog.state_path)


def _installed_pack(catalog: ModelCatalog, pack_id: str, version: str) -> InstalledPack:
    return next(
        item
        for item in catalog.installed()
        if item.id == pack_id and item.version == version
    )


def _download_moonshine_fast_pack(
    installer: HuggingFacePackInstaller,
    catalog: ModelCatalog,
) -> InstalledPack:
    """Prepara Moonshine Tiny Streaming EN + Marian Tiny INT8 de forma atómica."""

    definition = catalog.definition(_FAST_MOONSHINE_PACK)
    version = str(definition["version"])
    final_dir = catalog.packs_dir / _FAST_MOONSHINE_PACK / version
    if final_dir.is_dir() and installer.verify(_FAST_MOONSHINE_PACK, version):
        return _installed_pack(catalog, _FAST_MOONSHINE_PACK, version)

    try:
        from moonshine_voice import ModelArch, get_model_for_language
    except ImportError as exc:
        raise ModelOperationError(
            "MODEL_RUNTIME_ERROR",
            "El runtime privado no contiene Moonshine Voice.",
        ) from exc

    staging = catalog.models_dir / ".staging" / f"{_FAST_MOONSHINE_PACK}-{version}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    catalog.write_operation(
        state="installing",
        phase="download",
        message="Descargando Moonshine Tiny Streaming para inglés.",
        pack_id=_FAST_MOONSHINE_PACK,
        component="asr",
    )

    cache_root = catalog.models_dir / ".downloads" / "moonshine"
    cache_root.mkdir(parents=True, exist_ok=True)
    prior_cache = os.environ.get("MOONSHINE_VOICE_CACHE")
    os.environ["MOONSHINE_VOICE_CACHE"] = str(cache_root)
    try:
        model_path, model_arch = get_model_for_language(
            "en", ModelArch.TINY_STREAMING
        )
    except BaseException as exc:
        raise ModelOperationError(
            "MODEL_PROVIDER_ERROR",
            "Moonshine no pudo descargar el modelo streaming fijado.",
        ) from exc
    finally:
        if prior_cache is None:
            os.environ.pop("MOONSHINE_VOICE_CACHE", None)
        else:
            os.environ["MOONSHINE_VOICE_CACHE"] = prior_cache

    source = Path(model_path)
    if not source.is_dir():
        raise ModelOperationError(
            "MODEL_PROVIDER_ERROR",
            "Moonshine no entregó un directorio de modelo válido.",
        )
    asr_target = staging / "components" / "asr"
    shutil.copytree(source, asr_target, dirs_exist_ok=True)
    if not _moonshine_streaming_model_ready(asr_target):
        raise ModelOperationError(
            "MODEL_PROVIDER_ERROR",
            "El modelo Moonshine descargado está incompleto.",
        )
    (asr_target / "moonshine-config.json").write_text(
        json.dumps(
            {
                "modelArch": int(model_arch),
                "language": "en",
                "updateInterval": 0.45,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    catalog.write_operation(
        state="installing",
        phase="optimize",
        message="Preparando el traductor Marian Tiny INT8.",
        pack_id=_FAST_MOONSHINE_PACK,
        component="translation",
    )
    lite = installer.install("lite-en-es")
    lite_translation = lite.path / "components" / "translation"
    if not lite_translation.is_dir():
        raise ModelOperationError(
            "MODEL_CONVERSION_ERROR",
            "El traductor Lite no quedó preparado correctamente.",
        )
    shutil.copytree(
        lite_translation,
        staging / "components" / "translation",
        dirs_exist_ok=True,
    )

    (staging / "pack.json").write_text(
        json.dumps(
            {
                "schemaVersion": int(definition.get("schemaVersion", 2)),
                "id": _FAST_MOONSHINE_PACK,
                "version": version,
                "components": definition["components"],
                "files": _file_manifest(staging),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(final_dir, ignore_errors=True)
    staging.replace(final_dir)
    if not installer.verify(_FAST_MOONSHINE_PACK, version):
        shutil.rmtree(final_dir, ignore_errors=True)
        raise ModelOperationError(
            "MODEL_HASH_MISMATCH",
            "El pack Moonshine terminó de descargarse pero no pasó integridad.",
        )
    return _installed_pack(catalog, _FAST_MOONSHINE_PACK, version)


def _download_lite_zh_es_pack(
    installer: HuggingFacePackInstaller,
    catalog: ModelCatalog,
) -> InstalledPack:
    """Descarga Whisper Tiny multilingüe + ZH→EN→ES Marian y convierte MT a INT8."""

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise ModelOperationError(
            "MODEL_RUNTIME_ERROR",
            "El runtime privado no contiene huggingface_hub.",
        ) from exc

    definition = catalog.definition(_LITE_ZH_ES_PACK)
    version = str(definition["version"])
    final_dir = catalog.packs_dir / _LITE_ZH_ES_PACK / version
    if final_dir.is_dir() and installer.verify(_LITE_ZH_ES_PACK, version):
        return _installed_pack(catalog, _LITE_ZH_ES_PACK, version)

    staging = catalog.models_dir / ".staging" / f"{_LITE_ZH_ES_PACK}-{version}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    components = definition["components"]

    asr = components["asr"]
    asr_target = staging / "components" / "asr"
    catalog.write_operation(
        state="installing",
        phase="download",
        message="Descargando Whisper Tiny multilingüe para mandarín.",
        pack_id=_LITE_ZH_ES_PACK,
        component="asr",
    )
    snapshot_download(
        repo_id=asr["repoId"],
        revision=asr["revision"],
        local_dir=asr_target,
        allow_patterns=asr.get("allowPatterns"),
    )

    translation = components["translation"]
    stages = translation.get("stages", [])
    if len(stages) != 2:
        raise ModelOperationError(
            "MODEL_CASCADE_INVALID",
            "El pack ZH→ES Lite requiere exactamente dos etapas Marian.",
        )
    for index, stage in enumerate(stages, start=1):
        target = staging / "components" / "translation" / f"stage-{index}"
        catalog.write_operation(
            state="installing",
            phase="download",
            message=f"Descargando traductor Marian etapa {index}/2.",
            pack_id=_LITE_ZH_ES_PACK,
            component=f"translation-stage-{index}",
        )
        snapshot_download(
            repo_id=stage["repoId"],
            revision=stage["revision"],
            local_dir=target,
            allow_patterns=stage.get("allowPatterns"),
        )
        catalog.write_operation(
            state="installing",
            phase="optimize",
            message=f"Convirtiendo Marian etapa {index}/2 a CTranslate2 INT8.",
            pack_id=_LITE_ZH_ES_PACK,
            component=f"translation-stage-{index}",
        )
        _prepare_component(stage, target)

    (staging / "pack.json").write_text(
        json.dumps(
            {
                "schemaVersion": int(definition.get("schemaVersion", 2)),
                "id": _LITE_ZH_ES_PACK,
                "version": version,
                "components": components,
                "files": _file_manifest(staging),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(final_dir, ignore_errors=True)
    staging.replace(final_dir)
    if not installer.verify(_LITE_ZH_ES_PACK, version):
        shutil.rmtree(final_dir, ignore_errors=True)
        raise ModelOperationError(
            "MODEL_HASH_MISMATCH",
            "El pack ZH→ES Lite no pasó la verificación de integridad.",
        )
    return _installed_pack(catalog, _LITE_ZH_ES_PACK, version)


def download_pack(
    installer: HuggingFacePackInstaller,
    catalog: ModelCatalog,
    pack_id: str,
) -> InstalledPack:
    """Descarga/verifica un pack sin dejarlo activo."""

    previous_state = dict(catalog._state())
    try:
        if pack_id == _FAST_MOONSHINE_PACK:
            installed = _download_moonshine_fast_pack(installer, catalog)
        elif pack_id == _LITE_ZH_ES_PACK:
            installed = _download_lite_zh_es_pack(installer, catalog)
        else:
            installed = installer.install(pack_id)
        _restore_state(catalog, previous_state)
    except ModelOperationError:
        try:
            _restore_state(catalog, previous_state)
        except OSError:
            pass
        raise
    except BaseException as exc:
        try:
            _restore_state(catalog, previous_state)
        except OSError:
            pass
        raise ModelOperationError(
            "MODEL_STATE_RESTORE",
            "El modelo se descargó, pero no se pudo restaurar la selección anterior.",
        ) from exc

    return next(
        (
            item
            for item in catalog.installed()
            if item.id == installed.id and item.version == installed.version
        ),
        InstalledPack(
            id=installed.id,
            version=installed.version,
            path=installed.path,
            active=False,
            title=installed.title,
            commercial_use=installed.commercial_use,
        ),
    )
