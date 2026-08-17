"""Gestor de packs de modelos con staging, activación atómica y rollback."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_manifest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "pack.json"
    }


@dataclass(slots=True)
class InstalledPack:
    id: str
    version: str
    path: Path
    active: bool
    title: str
    commercial_use: bool


class ModelCatalog:
    def __init__(self, models_dir: Path, catalog_path: Path | None = None):
        self.models_dir = Path(models_dir)
        self.catalog_path = catalog_path or Path(__file__).with_name("model-packs.json")
        self.packs_dir = self.models_dir / "packs"
        self.state_path = self.models_dir / "current.json"

    def definitions(self) -> list[dict[str, Any]]:
        payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        if payload.get("schemaVersion") != 1 or not isinstance(payload.get("packs"), list):
            raise ValueError("Catálogo de modelos inválido")
        return payload["packs"]

    def definition(self, pack_id: str) -> dict[str, Any]:
        for pack in self.definitions():
            if pack.get("id") == pack_id:
                return pack
        raise KeyError(pack_id)

    def _state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"schemaVersion": 1, "active": None, "previous": None}
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"schemaVersion": 1, "active": None, "previous": None}
        return state

    def installed(self) -> list[InstalledPack]:
        active = self._state().get("active")
        installed: list[InstalledPack] = []
        if not self.packs_dir.exists():
            return installed
        definitions = {p["id"]: p for p in self.definitions()}
        for metadata_path in self.packs_dir.glob("*/*/pack.json"):
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            pack_id, version = metadata.get("id"), metadata.get("version")
            definition = definitions.get(pack_id, {})
            installed.append(InstalledPack(
                id=str(pack_id), version=str(version), path=metadata_path.parent,
                active=active == f"{pack_id}@{version}",
                title=str(definition.get("title", pack_id)),
                commercial_use=bool(definition.get("commercialUse", False)),
            ))
        return sorted(installed, key=lambda item: (item.id, item.version))

    def active_pack(self) -> InstalledPack | None:
        return next((item for item in self.installed() if item.active), None)


class HuggingFacePackInstaller:
    """Descarga snapshots completos a staging y solo activa cuando finalizan."""

    def __init__(self, catalog: ModelCatalog):
        self.catalog = catalog

    def install(self, pack_id: str) -> InstalledPack:
        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise RuntimeError("huggingface_hub no está instalado") from exc

        definition = self.catalog.definition(pack_id)
        version = str(definition["version"])
        final_dir = self.catalog.packs_dir / pack_id / version
        staging = self.catalog.models_dir / ".staging" / f"{pack_id}-{version}"
        if final_dir.exists():
            self.activate(pack_id, version)
            return next(item for item in self.catalog.installed() if item.id == pack_id and item.version == version)

        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True, exist_ok=True)
        try:
            for component_name, component in definition["components"].items():
                target = staging / "components" / component_name
                snapshot_download(
                    repo_id=component["repoId"],
                    revision=component.get("revision", "main"),
                    local_dir=target,
                )
            (staging / "pack.json").write_text(
                json.dumps({
                    "schemaVersion": 1,
                    "id": pack_id,
                    "version": version,
                    "components": definition["components"],
                    "files": _file_manifest(staging),
                }, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            final_dir.parent.mkdir(parents=True, exist_ok=True)
            staging.replace(final_dir)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        self.activate(pack_id, version)
        return next(item for item in self.catalog.installed() if item.id == pack_id and item.version == version)

    def verify(self, pack_id: str, version: str) -> bool:
        pack_dir = self.catalog.packs_dir / pack_id / version
        metadata_path = pack_dir / "pack.json"
        if not metadata_path.is_file():
            return False
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            expected = metadata.get("files", {})
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(expected, dict) or not expected:
            return False
        actual_files = {
            path.relative_to(pack_dir).as_posix(): path
            for path in pack_dir.rglob("*")
            if path.is_file() and path.name != "pack.json"
        }
        if set(actual_files) != set(expected):
            return False
        return all(_sha256(actual_files[relative]) == digest for relative, digest in expected.items())

    def activate(self, pack_id: str, version: str) -> None:
        pack_dir = self.catalog.packs_dir / pack_id / version
        if not (pack_dir / "pack.json").exists():
            raise FileNotFoundError("Pack no instalado")
        self.catalog.models_dir.mkdir(parents=True, exist_ok=True)
        state = self.catalog._state()
        new_ref = f"{pack_id}@{version}"
        previous = state.get("active") if state.get("active") != new_ref else state.get("previous")
        temp = self.catalog.state_path.with_suffix(".tmp")
        temp.write_text(json.dumps({"schemaVersion": 1, "active": new_ref, "previous": previous}, indent=2), encoding="utf-8")
        temp.replace(self.catalog.state_path)

    def rollback(self) -> InstalledPack:
        state = self.catalog._state()
        previous = state.get("previous")
        if not previous or "@" not in previous:
            raise RuntimeError("No existe un pack anterior para rollback")
        pack_id, version = previous.rsplit("@", 1)
        current = state.get("active")
        self.activate(pack_id, version)
        new_state = self.catalog._state()
        new_state["previous"] = current
        self.catalog.state_path.write_text(json.dumps(new_state, indent=2), encoding="utf-8")
        return self.catalog.active_pack()  # type: ignore[return-value]

    def remove(self, pack_id: str, version: str) -> None:
        ref = f"{pack_id}@{version}"
        if self.catalog._state().get("active") == ref:
            raise RuntimeError("No se puede eliminar el pack activo")
        shutil.rmtree(self.catalog.packs_dir / pack_id / version, ignore_errors=False)
