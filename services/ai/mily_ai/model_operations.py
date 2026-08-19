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
)

_FAST_MOONSHINE_PACK = "fast-moonshine-en-es"


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
    """Prepara Moonshine Tiny Streaming EN + Marian Tiny INT8 de forma atómica.

    Moonshine publica sus modelos ORT mediante su downloader oficial, no como el
    snapshot CT2 que usa el instalador histórico. El componente MT se reutiliza
    desde `lite-en-es`, por lo que no mantenemos dos conversores Marian.
    """

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
    required = ("encoder_model.ort", "decoder_model_merged.ort", "tokenizer.bin")
    if any(not (asr_target / name).is_file() for name in required):
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


def download_pack(
    installer: HuggingFacePackInstaller,
    catalog: ModelCatalog,
    pack_id: str,
) -> InstalledPack:
    """Descarga/verifica un pack sin dejarlo activo.

    El instalador histórico activa al terminar. Para Engine Hub, descargar y
    cargar son operaciones distintas: se restaura atómicamente el estado previo
    antes de devolver el pack instalado. Ningún peso queda cargado por esta
    función.
    """

    previous_state = dict(catalog._state())
    try:
        if pack_id == _FAST_MOONSHINE_PACK:
            installed = _download_moonshine_fast_pack(installer, catalog)
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
