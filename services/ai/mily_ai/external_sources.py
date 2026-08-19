"""Descarga segura de packs externos desde repositorios autorizados.

Engine Hub solo admite archivos ``.mmpack`` publicados por GitHub o Hugging
Face. La descarga queda en staging y después atraviesa la misma validación de
manifiesto, tipos de archivo, tamaños y SHA-256 que una importación local.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import SplitResult, urlsplit
from urllib.request import Request, urlopen

from .models import ModelOperationError

_DEFAULT_MAX_DOWNLOAD_BYTES = 4 * 1024 * 1024 * 1024
_ALLOWED_EXACT_HOSTS = {"github.com", "huggingface.co"}
_ALLOWED_HOST_SUFFIXES = (".githubusercontent.com", ".huggingface.co")


def _allowed_host(hostname: str) -> bool:
    host = hostname.casefold().rstrip(".")
    return host in _ALLOWED_EXACT_HOSTS or any(
        host.endswith(suffix) for suffix in _ALLOWED_HOST_SUFFIXES
    )


def _parse_external_url(url: str, *, require_mmpack: bool) -> SplitResult:
    candidate = str(url or "").strip()
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise ModelOperationError(
            "MODEL_EXTERNAL_SOURCE",
            "La URL del repositorio externo no es válida.",
        ) from exc
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or not _allowed_host(parsed.hostname)
    ):
        raise ModelOperationError(
            "MODEL_EXTERNAL_SOURCE",
            "Solo se permiten packs HTTPS de GitHub o Hugging Face.",
        )
    if require_mmpack and not parsed.path.casefold().endswith(".mmpack"):
        raise ModelOperationError(
            "MODEL_EXTERNAL_SOURCE",
            "La URL externa debe apuntar a un archivo .mmpack.",
        )
    return parsed


def validate_external_pack_url(url: str) -> str:
    """Valida la URL inicial sin resolverla ni enviar credenciales."""

    candidate = str(url or "").strip()
    _parse_external_url(candidate, require_mmpack=True)
    return candidate


def download_external_pack(
    url: str,
    staging_dir: Path,
    *,
    max_bytes: int = _DEFAULT_MAX_DOWNLOAD_BYTES,
    timeout_seconds: float = 60.0,
) -> Path:
    """Descarga por streaming y devuelve un `.mmpack` temporal verificado por origen."""

    source = validate_external_pack_url(url)
    limit = int(max_bytes)
    if limit <= 0:
        raise ValueError("max_bytes debe ser positivo")
    timeout = float(timeout_seconds)
    if timeout <= 0:
        raise ValueError("timeout_seconds debe ser positivo")
    root = Path(staging_dir)
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:20]
    target = root / f"external-{digest}.mmpack"
    temporary = target.with_suffix(".download")
    temporary.unlink(missing_ok=True)
    target.unlink(missing_ok=True)
    request = Request(
        source,
        headers={
            "User-Agent": "MilyVoiceTraductor-Engine-Hub/2.1",
            "Accept": "application/octet-stream",
        },
        method="GET",
    )
    downloaded = 0
    try:
        with urlopen(request, timeout=timeout) as response:  # nosec B310: HTTPS + host allowlist above.
            _parse_external_url(str(response.geturl()), require_mmpack=False)
            header = response.headers.get("Content-Length")
            if header:
                try:
                    declared = int(header)
                except ValueError:
                    declared = 0
                if declared < 0 or declared > limit:
                    raise ModelOperationError(
                        "MODEL_EXTERNAL_TOO_LARGE",
                        "El pack externo supera el límite permitido de descarga.",
                    )
            with temporary.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > limit:
                        raise ModelOperationError(
                            "MODEL_EXTERNAL_TOO_LARGE",
                            "El pack externo supera el límite permitido de descarga.",
                        )
                    output.write(chunk)
        if downloaded <= 0:
            raise ModelOperationError(
                "MODEL_EXTERNAL_INVALID",
                "El repositorio externo devolvió un archivo vacío.",
            )
        temporary.replace(target)
        return target
    except ModelOperationError:
        temporary.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        temporary.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise ModelOperationError(
            "MODEL_NO_NETWORK",
            "No se pudo descargar el pack desde el repositorio externo.",
        ) from exc
