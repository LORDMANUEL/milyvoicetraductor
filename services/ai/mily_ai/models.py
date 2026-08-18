"""Gestor de packs de modelos con staging, reanudación y activación atómica."""

from __future__ import annotations

import errno
import hashlib
import json
import shutil
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ModelOperationError(RuntimeError):
    """Error público estable; no contiene URLs privadas, tokens ni rutas del usuario."""

    code: str
    message: str

    def __str__(self) -> str:
        return self.message


def classify_model_exception(exc: BaseException) -> ModelOperationError:
    """Convierte excepciones de SO/red/HuggingFace a un contrato público estable."""
    if isinstance(exc, PermissionError):
        return ModelOperationError(
            "MODEL_PERMISSION_ERROR",
            "Windows no permitió escribir en la carpeta local de modelos.",
        )
    if isinstance(exc, OSError) and getattr(exc, "errno", None) == errno.ENOSPC:
        return ModelOperationError(
            "MODEL_NO_SPACE",
            "No hay suficiente espacio libre para completar el modelo.",
        )
    if isinstance(exc, (ConnectionError, socket.gaierror)):
        return ModelOperationError(
            "MODEL_NO_NETWORK",
            "No hay conexión disponible para continuar la descarga del modelo.",
        )
    if isinstance(exc, (TimeoutError, InterruptedError, KeyboardInterrupt)):
        return ModelOperationError(
            "MODEL_DOWNLOAD_INTERRUPTED",
            "La descarga se interrumpió. Puedes reintentar sin perder los archivos válidos.",
        )
    if isinstance(exc, ImportError):
        return ModelOperationError(
            "MODEL_RUNTIME_ERROR",
            "El runtime local no contiene una dependencia requerida para descargar modelos.",
        )

    name = exc.__class__.__name__.lower()
    text = str(exc).lower()
    if any(marker in name for marker in ("connection", "connect", "timeout")):
        return ModelOperationError(
            "MODEL_NO_NETWORK",
            "No se pudo conectar con el proveedor de modelos.",
        )
    if any(marker in name for marker in ("repositorynotfound", "revisionnotfound", "hfhubhttp")):
        return ModelOperationError(
            "MODEL_PROVIDER_ERROR",
            "El proveedor no pudo entregar la revisión fijada del modelo.",
        )
    if "no space left" in text or "disk full" in text:
        return ModelOperationError(
            "MODEL_NO_SPACE",
            "No hay suficiente espacio libre para completar el modelo.",
        )
    if any(marker in text for marker in ("connection", "network is unreachable", "name resolution", "offline")):
        return ModelOperationError(
            "MODEL_NO_NETWORK",
            "No hay conexión disponible para continuar la descarga del modelo.",
        )
    return ModelOperationError(
        "MODEL_PROVIDER_ERROR",
        "El proveedor de modelos no pudo completar la operación.",
    )


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


def _is_ctranslate2_model(path: Path) -> bool:
    return (path / "model.bin").is_file() and (path / "config.json").is_file()


def _is_m2m100_ready(path: Path) -> bool:
    tokenizer = path / "tokenizer"
    return (
        _is_ctranslate2_model(path)
        and (tokenizer / "config.json").is_file()
        and (tokenizer / "sentencepiece.bpe.model").is_file()
        and (tokenizer / "vocab.json").is_file()
    )


def _copy_hf_tokenizer(source_dir: Path, output_dir: Path) -> None:
    tokenizer_dir = output_dir / "tokenizer"
    tokenizer_dir.mkdir(parents=True, exist_ok=True)
    required = ("config.json", "sentencepiece.bpe.model", "vocab.json")
    optional = (
        "tokenizer_config.json",
        "special_tokens_map.json",
        "generation_config.json",
        "added_tokens.json",
    )
    for name in (*required, *optional):
        source = source_dir / name
        if source.is_file():
            shutil.copy2(source, tokenizer_dir / name)
    missing = [name for name in required if not (tokenizer_dir / name).is_file()]
    if missing:
        raise RuntimeError("faltan archivos requeridos del tokenizer M2M100")


def _convert_m2m100_to_ctranslate2(source_dir: Path, quantization: str = "int8") -> None:
    """Convierte el snapshot HF una vez y conserva el tokenizer HF por separado."""
    if _is_m2m100_ready(source_dir):
        return
    try:
        import ctranslate2
    except ImportError as exc:
        raise ModelOperationError(
            "MODEL_RUNTIME_ERROR",
            "El runtime local no contiene CTranslate2 para optimizar el modelo.",
        ) from exc

    output_dir = source_dir.with_name(source_dir.name + ".ct2")
    shutil.rmtree(output_dir, ignore_errors=True)
    try:
        converter = ctranslate2.converters.TransformersConverter(str(source_dir))
        converter.convert(
            str(output_dir),
            quantization=quantization,
            force=True,
        )
        if not _is_ctranslate2_model(output_dir):
            raise RuntimeError("la conversión no produjo model.bin/config.json")
        _copy_hf_tokenizer(source_dir, output_dir)
        if not _is_m2m100_ready(output_dir):
            raise RuntimeError("el pack convertido no contiene tokenizer utilizable")
        shutil.rmtree(source_dir)
        output_dir.replace(source_dir)
    except ModelOperationError:
        raise
    except BaseException as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise ModelOperationError(
            "MODEL_CONVERSION_ERROR",
            "El modelo se descargó, pero no pudo optimizarse para ejecución rápida en este equipo.",
        ) from exc


def _prepare_component(component: dict[str, Any], target: Path) -> None:
    provider = str(component.get("provider", ""))
    if provider == "m2m100-ct2":
        _convert_m2m100_to_ctranslate2(
            target,
            str(component.get("quantization", "int8")),
        )


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
        self.operation_path = self.models_dir / "operation.json"

    def write_operation(
        self,
        *,
        state: str,
        phase: str,
        message: str,
        pack_id: str,
        component: str | None = None,
        error_code: str | None = None,
    ) -> None:
        """Publica progreso seguro para la UI sin exponer rutas, tokens ni URLs firmadas."""
        self.models_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schemaVersion": 1,
            "state": state,
            "phase": phase,
            "message": message,
            "packId": pack_id,
            "component": component,
            "errorCode": error_code,
        }
        temp = self.operation_path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.operation_path)

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
            installed.append(
                InstalledPack(
                    id=str(pack_id),
                    version=str(version),
                    path=metadata_path.parent,
                    active=active == f"{pack_id}@{version}",
                    title=str(definition.get("title", pack_id)),
                    commercial_use=bool(definition.get("commercialUse", False)),
                )
            )
        return sorted(installed, key=lambda item: (item.id, item.version))

    def active_pack(self) -> InstalledPack | None:
        return next((item for item in self.installed() if item.active), None)


class HuggingFacePackInstaller:
    """Descarga a staging, reanuda y prepara componentes optimizados antes de activar."""

    def __init__(self, catalog: ModelCatalog):
        self.catalog = catalog

    @staticmethod
    def _download_message(component_name: str) -> str:
        if component_name == "asr":
            return "Descargando reconocimiento de voz Whisper Small desde Hugging Face."
        if component_name == "translation":
            return "Descargando traductor M2M100 desde Hugging Face."
        return "Descargando componente del modelo desde Hugging Face."

    def install(self, pack_id: str) -> InstalledPack:
        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            error = classify_model_exception(exc)
            self.catalog.write_operation(
                state="failed",
                phase="failed",
                message=error.message,
                pack_id=pack_id,
                error_code=error.code,
            )
            raise error from exc

        try:
            definition = self.catalog.definition(pack_id)
            version = str(definition["version"])
            final_dir = self.catalog.packs_dir / pack_id / version
            staging = self.catalog.models_dir / ".staging" / f"{pack_id}-{version}"
            self.catalog.write_operation(
                state="installing",
                phase="prepare",
                message="Preparando la instalación del modelo local.",
                pack_id=pack_id,
            )
            if final_dir.exists():
                self.catalog.write_operation(
                    state="installing",
                    phase="verify",
                    message="Verificando el modelo ya descargado.",
                    pack_id=pack_id,
                )
                if not self.verify(pack_id, version):
                    raise ModelOperationError(
                        "MODEL_HASH_MISMATCH",
                        "El modelo instalado no pasó la verificación de integridad.",
                    )
                self.activate(pack_id, version)
                self.catalog.write_operation(
                    state="ready",
                    phase="ready",
                    message="Modelo de tiempo real listo.",
                    pack_id=pack_id,
                )
                return next(
                    item
                    for item in self.catalog.installed()
                    if item.id == pack_id and item.version == version
                )

            staging.mkdir(parents=True, exist_ok=True)
            for component_name, component in definition["components"].items():
                target = staging / "components" / component_name
                if component.get("provider") == "m2m100-ct2":
                    if _is_ctranslate2_model(target) and not _is_m2m100_ready(target):
                        shutil.rmtree(target)
                    ready = _is_m2m100_ready(target)
                else:
                    ready = False
                if not ready:
                    self.catalog.write_operation(
                        state="installing",
                        phase="download",
                        message=self._download_message(component_name),
                        pack_id=pack_id,
                        component=component_name,
                    )
                    snapshot_download(
                        repo_id=component["repoId"],
                        revision=component.get("revision", "main"),
                        local_dir=target,
                        allow_patterns=component.get("allowPatterns"),
                    )
                if component.get("provider") == "m2m100-ct2":
                    self.catalog.write_operation(
                        state="installing",
                        phase="optimize",
                        message="Convirtiendo M2M100 a INT8 dentro de MilyVoiceTraductor. Los bytes pueden no cambiar durante esta fase.",
                        pack_id=pack_id,
                        component=component_name,
                    )
                _prepare_component(component, target)

            self.catalog.write_operation(
                state="installing",
                phase="verify",
                message="Verificando integridad del modelo preparado.",
                pack_id=pack_id,
            )
            (staging / "pack.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "id": pack_id,
                        "version": version,
                        "components": definition["components"],
                        "files": _file_manifest(staging),
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            final_dir.parent.mkdir(parents=True, exist_ok=True)
            if final_dir.exists():
                shutil.rmtree(final_dir)
            staging.replace(final_dir)
            if not self.verify(pack_id, version):
                raise ModelOperationError(
                    "MODEL_HASH_MISMATCH",
                    "La descarga terminó, pero la verificación de integridad falló.",
                )
            self.activate(pack_id, version)
            self.catalog.write_operation(
                state="ready",
                phase="ready",
                message="Modelo de tiempo real listo.",
                pack_id=pack_id,
            )
            return next(
                item
                for item in self.catalog.installed()
                if item.id == pack_id and item.version == version
            )
        except ModelOperationError as error:
            self.catalog.write_operation(
                state="failed",
                phase="failed",
                message=error.message,
                pack_id=pack_id,
                error_code=error.code,
            )
            raise
        except BaseException as exc:
            error = classify_model_exception(exc)
            self.catalog.write_operation(
                state="failed",
                phase="failed",
                message=error.message,
                pack_id=pack_id,
                error_code=error.code,
            )
            raise error from exc

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
        return all(
            _sha256(actual_files[relative]) == digest
            for relative, digest in expected.items()
        )

    def activate(self, pack_id: str, version: str) -> None:
        pack_dir = self.catalog.packs_dir / pack_id / version
        if not (pack_dir / "pack.json").exists():
            raise FileNotFoundError("Pack no instalado")
        self.catalog.models_dir.mkdir(parents=True, exist_ok=True)
        state = self.catalog._state()
        new_ref = f"{pack_id}@{version}"
        previous = (
            state.get("active")
            if state.get("active") != new_ref
            else state.get("previous")
        )
        temp = self.catalog.state_path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(
                {"schemaVersion": 1, "active": new_ref, "previous": previous}, indent=2
            ),
            encoding="utf-8",
        )
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
        self.catalog.state_path.write_text(
            json.dumps(new_state, indent=2), encoding="utf-8"
        )
        return self.catalog.active_pack()  # type: ignore[return-value]

    def remove(self, pack_id: str, version: str) -> None:
        ref = f"{pack_id}@{version}"
        if self.catalog._state().get("active") == ref:
            raise RuntimeError("No se puede eliminar el pack activo")
        shutil.rmtree(self.catalog.packs_dir / pack_id / version, ignore_errors=False)
