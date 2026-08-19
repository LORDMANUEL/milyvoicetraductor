"""Presupuesto de memoria estricto para MilyVoice Engine Hub.

El proceso completo de MilyVoice debe permanecer por debajo de 2 GiB. La memoria
compartida de una iGPU también sale de la RAM del sistema, por lo que se cuenta
contra el presupuesto efectivo del proceso antes de cargar un modelo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

ResourceMode = Literal["rescue", "lite", "balanced", "pressure", "rejected"]


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    """Límites expresados en MiB para evitar ambigüedad entre MB y MiB."""

    hard_process_mb: int = 2048
    rescue_mb: int = 700
    lite_steady_mb: int = 1200
    lite_peak_mb: int = 1536
    vram_budget_mb: int = 384

    def __post_init__(self) -> None:
        values = (
            self.hard_process_mb,
            self.rescue_mb,
            self.lite_steady_mb,
            self.lite_peak_mb,
            self.vram_budget_mb,
        )
        if any(value <= 0 for value in values):
            raise ValueError("Los límites de recursos deben ser positivos")
        if not self.rescue_mb <= self.lite_steady_mb <= self.lite_peak_mb <= self.hard_process_mb:
            raise ValueError("Los límites de RAM deben estar ordenados")
        if self.vram_budget_mb >= self.hard_process_mb:
            raise ValueError("El presupuesto VRAM no puede consumir todo el límite del proceso")


@dataclass(frozen=True, slots=True)
class RuntimeFootprint:
    """Uso observado o estimado antes de admitir una carga de modelo."""

    process_mb: float
    shared_gpu_mb: float = 0.0
    dedicated_vram_mb: float = 0.0

    def __post_init__(self) -> None:
        for value in (self.process_mb, self.shared_gpu_mb, self.dedicated_vram_mb):
            if not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError("El uso de memoria debe ser finito y no negativo")

    @property
    def effective_process_mb(self) -> float:
        return float(self.process_mb) + float(self.shared_gpu_mb)


@dataclass(frozen=True, slots=True)
class ResourceDecision:
    allowed: bool
    mode: ResourceMode
    reason: str
    effective_process_mb: float
    dedicated_vram_mb: float
    process_headroom_mb: float
    vram_headroom_mb: float


class ResourceGovernor:
    """Autoriza modelos y decide degradación antes de agotar Windows."""

    def __init__(self, limits: ResourceLimits | None = None):
        self.limits = limits or ResourceLimits()

    def _mode_for(self, effective_mb: float) -> ResourceMode:
        if effective_mb <= self.limits.rescue_mb:
            return "rescue"
        if effective_mb <= self.limits.lite_steady_mb:
            return "lite"
        if effective_mb <= self.limits.lite_peak_mb:
            return "balanced"
        return "pressure"

    def evaluate(self, footprint: RuntimeFootprint) -> ResourceDecision:
        effective = footprint.effective_process_mb
        process_headroom = self.limits.hard_process_mb - effective
        vram_headroom = self.limits.vram_budget_mb - float(footprint.dedicated_vram_mb)

        if effective > self.limits.hard_process_mb:
            return ResourceDecision(
                allowed=False,
                mode="rejected",
                reason="PROCESS_MEMORY_LIMIT",
                effective_process_mb=effective,
                dedicated_vram_mb=float(footprint.dedicated_vram_mb),
                process_headroom_mb=process_headroom,
                vram_headroom_mb=vram_headroom,
            )
        if float(footprint.dedicated_vram_mb) > self.limits.vram_budget_mb:
            return ResourceDecision(
                allowed=False,
                mode="rejected",
                reason="VRAM_LIMIT",
                effective_process_mb=effective,
                dedicated_vram_mb=float(footprint.dedicated_vram_mb),
                process_headroom_mb=process_headroom,
                vram_headroom_mb=vram_headroom,
            )
        return ResourceDecision(
            allowed=True,
            mode=self._mode_for(effective),
            reason="OK",
            effective_process_mb=effective,
            dedicated_vram_mb=float(footprint.dedicated_vram_mb),
            process_headroom_mb=process_headroom,
            vram_headroom_mb=vram_headroom,
        )

    def can_load(
        self,
        *,
        current_process_mb: float,
        model_ram_mb: float,
        shared_gpu_mb: float = 0.0,
        dedicated_vram_mb: float = 0.0,
    ) -> ResourceDecision:
        """Comprueba una carga estimada antes de reservar memoria nativa."""

        for value in (current_process_mb, model_ram_mb, shared_gpu_mb, dedicated_vram_mb):
            if not math.isfinite(float(value)) or float(value) < 0:
                raise ValueError("El presupuesto de carga debe ser finito y no negativo")
        return self.evaluate(
            RuntimeFootprint(
                process_mb=float(current_process_mb) + float(model_ram_mb),
                shared_gpu_mb=float(shared_gpu_mb),
                dedicated_vram_mb=float(dedicated_vram_mb),
            )
        )
