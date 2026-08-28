"""Operaciones de descarga exclusivas de las rutas Tier 1 añadidas en 2.1.

El descargador estable permanece intacto. Esta capa sólo intercepta packs que
realmente declaran una cascada Marian de dos etapas y delega el resto al módulo base.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .model_operations import download_pack as stable_download_pack
from .models import (
    HuggingFacePackInstaller,
    InstalledPack,
    ModelCatalog,
    ModelOperationError,
    _file_manifest,
    _prepare_component,
)

_LITE_ES_ZH_PACK = "lite-es-zh"
_TIER1_CASCADE_PACKS = {_LITE_ES_ZH_PACK}


def _restore_state(catalog: ModelCatalog, state: dict[str, Any]) -> None:
    catalog.models_dir.mkdir(parents=True, exist_ok=True)
    temporary = catalog.state_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(catalog.state_path)


def _installed_pack(
    catalog: ModelCatalog, pack_id: str, version: str
) -> InstalledPack:
    return next(
        item
        for item in catalog.installed()
        if item.id == pack_id and item.version == version
    )


def _download_lite_cascade_pack(
    installer: HuggingFacePackInstaller,
    catalog: ModelCatalog,
    pack_id: str,
) -> InstalledPack:
    """Descarga ASR + dos etapas Marian y deja un pack verificado en disco."""

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise ModelOperationError(
            "MODEL_RUNTIME_ERROR",
            "El runtime privado no contiene huggingface_hub.",
        ) from exc

    definition = catalog.definition(pack_id)
    if str(definition.get("tier", "")) != "lite":
        raise ModelOperationError(
            "MODEL_CASCADE_INVALID",
            "La cascada Tier 1 debe pertenecer al perfil Lite.",
        )
    version = str(definition["version"])
    final_dir = catalog.packs_dir / pack_id / version
    if final_dir.is_dir() and installer.verify(pack_id, version):
        return _installed_pack(catalog, pack_id, version)

    components = definition.get("components")
    if not isinstance(components, dict):
        raise ModelOperationError(
            "MODEL_CASCADE_INVALID",
            "El pack Tier 1 no declara componentes válidos.",
        )
    asr = components.get("asr")
    translation = components.get("translation")
    if not isinstance(asr, dict) or not isinstance(translation, dict):
        raise ModelOperationError(
            "MODEL_CASCADE_INVALID",
            "El pack Tier 1 requiere ASR y traducción.",
        )
    if str(translation.get("provider", "")) != "marian-cascade-ct2":
        raise ModelOperationError(
            "MODEL_CASCADE_INVALID",
            "El pack Tier 1 no declara una cascada Marian válida.",
        )
    stages = translation.get("stages")
    if not isinstance(stages, list) or len(stages) != 2:
        raise ModelOperationError(
            "MODEL_CASCADE_INVALID",
            "La cascada Tier 1 requiere exactamente dos etapas Marian.",
        )

    first, second = stages
    if not isinstance(first, dict) or not isinstance(second, dict):
        raise ModelOperationError(
            "MODEL_CASCADE_INVALID",
            "Las etapas de traducción no son válidas.",
        )
    source = str(first.get("sourceLanguage", "")).strip().lower()
    pivot = str(first.get("targetLanguage", "")).strip().lower()
    second_source = str(second.get("sourceLanguage", "")).strip().lower()
    target_language = str(second.get("targetLanguage", "")).strip().lower()
    route = str((definition.get("routes") or [""])[0]).strip().lower()
    if not source or not pivot or pivot != second_source or not target_language:
        raise ModelOperationError(
            "MODEL_CASCADE_INVALID",
            "Las etapas Marian no forman una ruta continua.",
        )
    if route != f"{source}-{target_language}":
        raise ModelOperationError(
            "MODEL_CASCADE_INVALID",
            "La cascada Marian no coincide con la ruta declarada del pack.",
        )

    staging = catalog.models_dir / ".staging" / f"{pack_id}-{version}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)

    asr_target = staging / "components" / "asr"
    catalog.write_operation(
        state="installing",
        phase="download",
        message=f"Descargando reconocimiento de voz para {source.upper()}.",
        pack_id=pack_id,
        component="asr",
    )
    snapshot_download(
        repo_id=asr["repoId"],
        revision=asr["revision"],
        local_dir=asr_target,
        allow_patterns=asr.get("allowPatterns"),
    )

    for index, stage in enumerate(stages, start=1):
        stage_target = staging / "components" / "translation" / f"stage-{index}"
        catalog.write_operation(
            state="installing",
            phase="download",
            message=f"Descargando traductor Marian etapa {index}/2.",
            pack_id=pack_id,
            component=f"translation-stage-{index}",
        )
        snapshot_download(
            repo_id=stage["repoId"],
            revision=stage["revision"],
            local_dir=stage_target,
            allow_patterns=stage.get("allowPatterns"),
        )
        catalog.write_operation(
            state="installing",
            phase="optimize",
            message=f"Convirtiendo Marian etapa {index}/2 a CTranslate2 INT8.",
            pack_id=pack_id,
            component=f"translation-stage-{index}",
        )
        _prepare_component(stage, stage_target)

    (staging / "pack.json").write_text(
        json.dumps(
            {
                "schemaVersion": int(definition.get("schemaVersion", 2)),
                "id": pack_id,
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
    if not installer.verify(pack_id, version):
        shutil.rmtree(final_dir, ignore_errors=True)
        raise ModelOperationError(
            "MODEL_HASH_MISMATCH",
            "El pack Tier 1 no pasó la verificación de integridad.",
        )
    return _installed_pack(catalog, pack_id, version)


def download_pack(
    installer: HuggingFacePackInstaller,
    catalog: ModelCatalog,
    pack_id: str,
) -> InstalledPack:
    """Intercepta cascadas Tier 1 y conserva la selección previa."""

    if pack_id not in _TIER1_CASCADE_PACKS:
        return stable_download_pack(installer, catalog, pack_id)
    definition = catalog.definition(pack_id)
    components = definition.get("components")
    translation = components.get("translation") if isinstance(components, dict) else None
    if not isinstance(translation, dict) or str(translation.get("provider", "")) != "marian-cascade-ct2":
        return stable_download_pack(installer, catalog, pack_id)

    previous_state = dict(catalog._state())
    try:
        installed = _download_lite_cascade_pack(installer, catalog, pack_id)
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
            path=Path(installed.path),
            active=False,
            title=installed.title,
            commercial_use=installed.commercial_use,
        ),
    )
