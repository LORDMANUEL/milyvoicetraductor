"""Selección ejecutable y conservadora de backend para proveedores locales.

Este módulo no confunde presencia de GPU con compatibilidad. El caller entrega
el número real de dispositivos CUDA que reporta CTranslate2 y una función que
intenta cargar el proveedor en el dispositivo solicitado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class BackendLoadError(RuntimeError):
    """Fallo público de selección/carga de un backend de cómputo."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class BackendLoadResult(Generic[T]):
    """Proveedor cargado y evidencia mínima de la decisión tomada."""

    device: str
    value: T
    fallback_used: bool = False
    reason: str = ""


def _safe_reason(error: BaseException) -> str:
    """Registra solo clase del fallo; no filtra rutas, tokens ni stderr crudo."""

    return error.__class__.__name__


def _load_cpu(loader: Callable[[str], T], *, fallback_reason: str = "") -> BackendLoadResult[T]:
    try:
        value = loader("cpu")
    except Exception as exc:  # noqa: BLE001 - se normaliza en error público seguro.
        raise BackendLoadError(
            "CPU_INIT_FAILED",
            "No se pudo iniciar el backend CPU local.",
        ) from exc
    return BackendLoadResult(
        device="cpu",
        value=value,
        fallback_used=bool(fallback_reason),
        reason=fallback_reason,
    )


def load_backend_with_fallback(
    compute_profile: str,
    cuda_device_count: int,
    loader: Callable[[str], T],
) -> BackendLoadResult[T]:
    """Carga CPU/CUDA respetando el perfil y con fallback seguro en ``auto``.

    Reglas:
    - ``cpu`` nunca toca CUDA;
    - ``auto`` prueba CUDA solo si CTranslate2 reportó un dispositivo real;
    - ``auto`` cae a CPU cuando la carga CUDA falla;
    - ``gpu`` es estricto: ausencia o fallo CUDA se informa, no se oculta;
    - cualquier perfil desconocido se trata como ``auto`` por seguridad.
    """

    profile = (compute_profile or "auto").strip().lower()
    if profile not in {"auto", "cpu", "gpu"}:
        profile = "auto"

    count = max(0, int(cuda_device_count or 0))
    if profile == "cpu":
        return _load_cpu(loader)

    if count <= 0:
        if profile == "gpu":
            raise BackendLoadError(
                "CUDA_UNAVAILABLE",
                "Se solicitó GPU, pero CTranslate2 no detectó un dispositivo CUDA utilizable.",
            )
        return _load_cpu(loader)

    try:
        value = loader("cuda")
        return BackendLoadResult(device="cuda", value=value)
    except Exception as exc:  # noqa: BLE001 - la carga del runtime puede fallar de varias formas.
        if profile == "gpu":
            raise BackendLoadError(
                "CUDA_INIT_FAILED",
                "CTranslate2 detectó CUDA, pero no pudo inicializar el backend GPU.",
            ) from exc
        return _load_cpu(loader, fallback_reason=f"cuda:{_safe_reason(exc)}")
