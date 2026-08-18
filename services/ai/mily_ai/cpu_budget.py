"""Presupuesto conservador de CPU para ASR y traducción en tiempo real.

El objetivo no es consumir todos los hilos lógicos disponibles, sino repartir los
núcleos físicos entre las etapas pesadas sin sobresuscribir el procesador. La
arquitectura posterior puede ejecutar ASR y traducción en paralelo usando este
mismo contrato.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CpuBudget:
    """Distribución de núcleos para las etapas de inferencia local."""

    profile: str
    physical_cores: int
    asr_threads: int
    translation_threads: int
    parallel_stages: bool


def _positive_int(value: object) -> int | None:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _physical_cores(explicit: int | None) -> int:
    """Obtiene un conteo físico conservador y nunca devuelve menos de uno."""

    if (value := _positive_int(explicit)) is not None:
        return value
    if (value := _positive_int(os.environ.get("MILY_PHYSICAL_CPUS"))) is not None:
        return value
    logical = max(1, os.cpu_count() or 1)
    # Sin una API física portátil dentro del sidecar, asumir SMT x2 evita
    # asignar dos trabajos AVX/INT8 pesados al mismo núcleo físico.
    return max(1, logical // 2)


def detect_cpu_budget(profile: str = "balanced", physical_cores: int | None = None) -> CpuBudget:
    """Calcula threads de ASR/traducción sin exceder núcleos físicos.

    Perfiles:
    - ``light``: reserva CPU para equipos modestos y limita inferencia a 2 núcleos.
    - ``balanced``: deja aproximadamente un núcleo libre para UI/audio/SO.
    - ``max``: permite usar el presupuesto físico completo.
    """

    normalized = (profile or "balanced").strip().lower()
    if normalized not in {"light", "balanced", "max"}:
        normalized = "balanced"

    physical = _physical_cores(physical_cores)
    if normalized == "light":
        compute = min(2, physical)
    elif normalized == "max":
        compute = physical
    else:
        compute = max(1, physical - 1)

    parallel = compute >= 2
    if not parallel:
        return CpuBudget(
            profile=normalized,
            physical_cores=physical,
            asr_threads=1,
            translation_threads=1,
            parallel_stages=False,
        )

    asr_threads = max(1, round(compute * 0.65))
    translation_threads = max(1, compute - asr_threads)

    while asr_threads + translation_threads > physical and asr_threads > 1:
        asr_threads -= 1
    while asr_threads + translation_threads > physical and translation_threads > 1:
        translation_threads -= 1

    return CpuBudget(
        profile=normalized,
        physical_cores=physical,
        asr_threads=asr_threads,
        translation_threads=translation_threads,
        parallel_stages=True,
    )
