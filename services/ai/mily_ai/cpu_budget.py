"""Presupuesto conservador de CPU para ASR y traducción en tiempo real.

El objetivo no es consumir todos los hilos lógicos disponibles, sino repartir los
núcleos físicos entre las etapas pesadas sin sobresuscribir el procesador. Rust
inyecta la topología física real al sidecar mediante ``MILY_PHYSICAL_CPUS`` en la
instalación normal; el fallback SMT se conserva para ejecución independiente.
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
    # Fallback únicamente para sidecars lanzados fuera de MilyVoice. El runtime
    # instalado pasa el conteo físico real desde Rust y evita esta aproximación.
    return max(1, logical // 2)


def detect_cpu_budget(profile: str = "balanced", physical_cores: int | None = None) -> CpuBudget:
    """Calcula threads de ASR/traducción sin exceder núcleos físicos.

    Perfiles:
    - ``light``: limita trabajo concurrente a dos núcleos.
    - ``balanced``: reserva capacidad para UI/audio en >=3 cores. En equipos
      dual-core reutiliza ambos cores para ASR y ejecuta traducción de forma
      serial para no convertir un Haswell 2C/4T en un equipo de un solo core.
    - ``max``: permite usar el presupuesto físico completo en paralelo.
    """

    normalized = (profile or "balanced").strip().lower()
    if normalized not in {"light", "balanced", "max"}:
        normalized = "balanced"

    physical = _physical_cores(physical_cores)

    if physical == 1:
        return CpuBudget(
            profile=normalized,
            physical_cores=1,
            asr_threads=1,
            translation_threads=1,
            parallel_stages=False,
        )

    # El perfil objetivo para i3 Haswell 2C/4T debe usar ambos cores en Whisper,
    # pero no ejecutar Whisper y MT pesados simultáneamente. La traducción Tiny
    # futura también hereda este contrato sin cambiar la API.
    if normalized == "balanced" and physical == 2:
        return CpuBudget(
            profile=normalized,
            physical_cores=physical,
            asr_threads=2,
            translation_threads=1,
            parallel_stages=False,
        )

    if normalized == "light":
        compute = min(2, physical)
    elif normalized == "max":
        compute = physical
    else:
        compute = max(2, physical - 1)

    parallel = compute >= 2
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
        parallel_stages=parallel,
    )
