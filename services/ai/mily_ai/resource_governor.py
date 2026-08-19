"""Presupuesto de memoria estricto para MilyVoice Engine Hub.

El límite de 2 GiB se aplica al producto completo: motor Python, aplicación de
escritorio, bridge nativo, sidecars y memoria compartida de una iGPU. La VRAM
dedicada se controla por separado para conservar margen al sistema y navegador.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

ResourceMode = Literal["rescue", "lite", "balanced", "pressure", "rejected"]


def _validate_memory(values: tuple[float | int, ...], message: str) -> None:
    if any(
        not math.isfinite(float(value)) or float(value) < 0 for value in values
    ):
        raise ValueError(message)


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    """Límites y reservas del producto expresados en MiB."""

    hard_process_mb: int = 2048
    rescue_mb: int = 700
    lite_steady_mb: int = 1200
    lite_peak_mb: int = 1536
    vram_budget_mb: int = 384
    desktop_reserve_mb: int = 256
    bridge_reserve_mb: int = 64

    def __post_init__(self) -> None:
        values = (
            self.hard_process_mb,
            self.rescue_mb,
            self.lite_steady_mb,
            self.lite_peak_mb,
            self.vram_budget_mb,
            self.desktop_reserve_mb,
            self.bridge_reserve_mb,
        )
        if any(value <= 0 for value in values):
            raise ValueError(
                "Los límites y reservas de recursos deben ser positivos"
            )
        if not (
            self.rescue_mb
            <= self.lite_steady_mb
            <= self.lite_peak_mb
            <= self.hard_process_mb
        ):
            raise ValueError("Los límites de RAM deben estar ordenados")
        if self.vram_budget_mb >= self.hard_process_mb:
            raise ValueError(
                "El presupuesto VRAM no puede consumir todo el límite del producto"
            )
        if self.product_reserve_mb >= self.hard_process_mb:
            raise ValueError(
                "Las reservas base no pueden consumir todo el límite del producto"
            )

    @property
    def product_reserve_mb(self) -> int:
        return self.desktop_reserve_mb + self.bridge_reserve_mb


@dataclass(frozen=True, slots=True)
class RuntimeFootprint:
    """Memoria residente observada o estimada de todos los procesos MilyVoice."""

    process_mb: float
    shared_gpu_mb: float = 0.0
    dedicated_vram_mb: float = 0.0
    desktop_mb: float = 0.0
    bridge_mb: float = 0.0
    child_process_mb: float = 0.0

    def __post_init__(self) -> None:
        _validate_memory(
            (
                self.process_mb,
                self.shared_gpu_mb,
                self.dedicated_vram_mb,
                self.desktop_mb,
                self.bridge_mb,
                self.child_process_mb,
            ),
            "El uso de memoria debe ser finito y no negativo",
        )

    @property
    def effective_process_mb(self) -> float:
        return sum(
            float(value)
            for value in (
                self.process_mb,
                self.desktop_mb,
                self.bridge_mb,
                self.child_process_mb,
                self.shared_gpu_mb,
            )
        )


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
    """Autoriza cargas y degrada funciones antes de agotar Windows."""

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
        vram_headroom = self.limits.vram_budget_mb - float(
            footprint.dedicated_vram_mb
        )

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

    def preflight_model(
        self,
        *,
        model_ram_mb: float,
        current_process_mb: float = 0.0,
        desktop_mb: float | None = None,
        bridge_mb: float | None = None,
        child_process_mb: float = 0.0,
        shared_gpu_mb: float = 0.0,
        dedicated_vram_mb: float = 0.0,
    ) -> ResourceDecision:
        """Evalúa un modelo antes de cargarlo usando reservas conservadoras."""

        _validate_memory(
            (
                model_ram_mb,
                current_process_mb,
                child_process_mb,
                shared_gpu_mb,
                dedicated_vram_mb,
            ),
            "El presupuesto de carga debe ser finito y no negativo",
        )
        desktop = (
            self.limits.desktop_reserve_mb if desktop_mb is None else desktop_mb
        )
        bridge = self.limits.bridge_reserve_mb if bridge_mb is None else bridge_mb
        _validate_memory(
            (desktop, bridge), "Las reservas deben ser finitas y no negativas"
        )
        return self.evaluate(
            RuntimeFootprint(
                process_mb=float(current_process_mb) + float(model_ram_mb),
                desktop_mb=float(desktop),
                bridge_mb=float(bridge),
                child_process_mb=float(child_process_mb),
                shared_gpu_mb=float(shared_gpu_mb),
                dedicated_vram_mb=float(dedicated_vram_mb),
            )
        )

    def can_load(
        self,
        *,
        current_process_mb: float,
        model_ram_mb: float,
        shared_gpu_mb: float = 0.0,
        dedicated_vram_mb: float = 0.0,
        desktop_mb: float | None = None,
        bridge_mb: float | None = None,
        child_process_mb: float = 0.0,
    ) -> ResourceDecision:
        """Comprueba una carga estimada antes de reservar memoria nativa."""

        return self.preflight_model(
            current_process_mb=current_process_mb,
            model_ram_mb=model_ram_mb,
            shared_gpu_mb=shared_gpu_mb,
            dedicated_vram_mb=dedicated_vram_mb,
            desktop_mb=desktop_mb,
            bridge_mb=bridge_mb,
            child_process_mb=child_process_mb,
        )
