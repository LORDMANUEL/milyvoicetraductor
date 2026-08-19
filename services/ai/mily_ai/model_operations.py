"""Operaciones de modelo que separan descarga en disco de activación en memoria."""

from __future__ import annotations

import json
from typing import Any

from .models import HuggingFacePackInstaller, InstalledPack, ModelCatalog, ModelOperationError


def _restore_state(catalog: ModelCatalog, state: dict[str, Any]) -> None:
    catalog.models_dir.mkdir(parents=True, exist_ok=True)
    temp = catalog.state_path.with_suffix(".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(catalog.state_path)


def download_pack(
    installer: HuggingFacePackInstaller,
    catalog: ModelCatalog,
    pack_id: str,
) -> InstalledPack:
    """Descarga/verifica un pack sin dejarlo activo.

    El instalador histórico activa al terminar. Para Engine Hub, descargar y
    cargar son operaciones distintas: se restaura atómicamente el estado previo
    antes de devolver el pack instalado. Ningún peso se abre por esta función.
    """

    previous_state = dict(catalog._state())
    try:
        installed = installer.install(pack_id)
        _restore_state(catalog, previous_state)
    except ModelOperationError:
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
