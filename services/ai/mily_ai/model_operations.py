"""Operaciones de modelo que separan descarga en disco de activación en memoria."""

from __future__ import annotations

import json
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
_MOONSHINE_NON_STREAMING_REQUIRED = (
    "encoder_model.ort",
    "decoder_model_merged.ort",
    "tokenizer.bin",
)
_MOONSHINE_STREAMING_REQUIRED = (
    "frontend.ort",
    "encoder.ort",
    "adapter.ort",
    "cross_kv.ort",
    "decoder_kv.ort",
    "streaming_config.json",
    "tokenizer.bin",
)
_MOONSHINE_NON_STREAMING_ATTENTION = "decoder_model_merged_with_attention.ort"
_MOONSHINE_STREAMING_ATTENTION = "decoder_kv_with_attention.ort"


def _moonshine_arch_name(model_arch: object) -> str:
    name = str(getattr(model_arch, "name", "") or "").strip().upper()
    if name:
        return name
    return str(model_arch).strip().upper()


def _moonshine_required_files(
    model_arch: object,
    *,
    include_word_timestamps: bool = False,
) -> tuple[str, ...]:
    """Devuelve el layout oficial según la arquitectura Moonshine descargada."""

    streaming = "STREAMING" in _moonshine_arch_name(model_arch)
    required = list(
        _MOONSHINE_STREAMING_REQUIRED
        if streaming
        else _MOONSHINE_NON_STREAMING_REQUIRED
    )
    if include_word_timestamps:
        required.append(
            _MOONSHINE_STREAMING_ATTENTION
            if streaming
            else _MOONSHINE_NON_STREAMING_ATTENTION
        )
    return tuple(required)


def _copy_moonshine_model_assets(
    source: Path,
    target: Path,
    model_arch: object,
    *,
    include_word_timestamps: bool = False,
) -> tuple[str, ...]:
    """Copia únicamente archivos de inferencia; excluye spelling/TTS opcionales."""

    source = Path(source)
    target = Path(target)
    required = _moonshine_required_files(
        model_arch,
        include_word_timestamps=include_word_timestamps,
    )
    missing = sorted(name for name in required if not (source / name).is_file())
    if missing:
        raise ModelOperationError(
            "MODEL_PROVIDER_ERROR",
            "El modelo Moonshine descargado está incompleto; faltan: "
            + ", ".join(missing)
            + ".",
        )

    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    try:
        for name in required:
            shutil.copy2(source / name, target / name)
    except OSError as exc:
        shutil.rmtree(target, ignore_errors=True)
        raise ModelOperationError(
            "MODEL_PROVIDER_ERROR",
            "Moonshine no pudo preparar los archivos locales de inferencia.",
        ) from exc
    return required


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
        from moonshine_voice import ModelArch
        from moonshine_voice.download import (
            download_model_from_info,
            find_model_info,
        )
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
    include_word_timestamps = True
    try:
        model_info = find_model_info("en", ModelArch.TINY_STREAMING)
        model_path, model_arch = download_model_from_info(
            model_info,
            cache_root=cache_root,
            include_word_timestamps=include_word_timestamps,
        )
    except BaseException as exc:
        raise ModelOperationError(
            "MODEL_PROVIDER_ERROR",
            "Moonshine no pudo descargar el modelo streaming fijado.",
        ) from exc

    source = Path(model_path)
    if not source.is_dir():
        raise ModelOperationError(
            "MODEL_PROVIDER_ERROR",
            "Moonshine no entregó un directorio de modelo válido.",
        )
    asr_target = staging / "components" / "asr"
    _copy_moonshine_model_assets(
        source,
        asr_target,
        model_arch,
        include_word_timestamps=include_word_timestamps,
    )
    (asr_target / "moonshine-config.json").write_text(
        json.dumps(
            {
                "modelArch": int(model_arch),
                "language": "en",
                "updateInterval": 0.45,
                "wordTimestampsAvailable": include_word_timestamps,
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
