"""Registro y selección automática de motores por evidencia medible."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .resource_governor import ResourceGovernor, RuntimeFootprint


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    rtf: float
    p95_ms: float
    p50_ms: float = 0.0
    stable: bool = True

    def __post_init__(self) -> None:
        values = (self.rtf, self.p95_ms, self.p50_ms)
        if not all(
            math.isfinite(float(value)) and float(value) >= 0
            for value in values
        ):
            raise ValueError(
                "Las métricas de benchmark deben ser finitas y no negativas"
            )


@dataclass(frozen=True, slots=True)
class EngineDescriptor:
    id: str
    kind: str
    title: str
    routes: tuple[str, ...]
    runtime: str
    cloud: bool
    commercial_use: bool


@dataclass(frozen=True, slots=True)
class EngineCandidate:
    id: str
    engine_id: str
    ram_mb: float
    vram_mb: float
    quality_score: float
    benchmark: BenchmarkSample
    backends: tuple[str, ...] = ()
    shared_gpu_mb: float = 0.0
    total_product_mb: float = 0.0

    def __post_init__(self) -> None:
        if not self.id or not self.engine_id:
            raise ValueError("El candidato debe tener id y engine_id")
        memory = (
            self.ram_mb,
            self.vram_mb,
            self.shared_gpu_mb,
            self.total_product_mb,
        )
        if not all(
            math.isfinite(float(value)) and float(value) >= 0
            for value in memory
        ):
            raise ValueError("La memoria del candidato debe ser finita y no negativa")
        if (
            not math.isfinite(float(self.quality_score))
            or not 0 <= float(self.quality_score) <= 1
        ):
            raise ValueError("quality_score debe estar entre cero y uno")


@dataclass(frozen=True, slots=True)
class EngineSelection:
    candidate: EngineCandidate
    backend: str
    score: float
    rejected: dict[str, str] = field(default_factory=dict)


def load_engine_descriptors(
    path: Path | None = None,
) -> tuple[EngineDescriptor, ...]:
    catalog_path = path or Path(__file__).with_name("engine-families.json")
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != 1 or not isinstance(
        payload.get("engines"), list
    ):
        raise ValueError("Catálogo de motores inválido")
    output: list[EngineDescriptor] = []
    seen: set[str] = set()
    for item in payload["engines"]:
        engine_id = str(item.get("id", "")).strip()
        if not engine_id or engine_id in seen:
            raise ValueError("Los ids de motores deben ser únicos")
        routes = tuple(str(route) for route in item.get("routes", ()))
        if not routes:
            raise ValueError("Cada motor debe declarar al menos una ruta")
        seen.add(engine_id)
        output.append(
            EngineDescriptor(
                id=engine_id,
                kind=str(item.get("kind", "pipeline")),
                title=str(item.get("title", engine_id)),
                routes=routes,
                runtime=str(item.get("runtime", "builtin")),
                cloud=bool(item.get("cloud", False)),
                commercial_use=bool(item.get("commercialUse", False)),
            )
        )
    return tuple(output)


class EngineRegistry:
    """Filtra incompatibilidades y elige el motor con mejor balance medido."""

    def __init__(
        self,
        resource_governor: ResourceGovernor,
        *,
        descriptors: Iterable[EngineDescriptor] = (),
    ):
        items = tuple(descriptors)
        self.resource_governor = resource_governor
        self._descriptors = {descriptor.id: descriptor for descriptor in items}
        if len(self._descriptors) != len(items):
            raise ValueError("Los ids de motores deben ser únicos")

    @property
    def descriptors(self) -> tuple[EngineDescriptor, ...]:
        return tuple(self._descriptors.values())

    def _score(self, candidate: EngineCandidate) -> float:
        benchmark = candidate.benchmark
        if not benchmark.stable:
            return float("-inf")
        speed = max(0.0, 1.5 - float(benchmark.rtf)) / 1.5
        latency = 1.0 / (1.0 + float(benchmark.p95_ms) / 1000.0)
        total_ram_mb = (
            float(candidate.total_product_mb)
            if candidate.total_product_mb > 0
            else (
                float(candidate.ram_mb)
                + float(candidate.shared_gpu_mb)
                + float(self.resource_governor.limits.product_reserve_mb)
            )
        )
        memory = 1.0 / (1.0 + total_ram_mb / 1024.0)
        return (
            0.42 * speed
            + 0.30 * latency
            + 0.20 * float(candidate.quality_score)
            + 0.08 * memory
        )

    def select(
        self,
        *,
        route: str,
        candidates: Iterable[EngineCandidate],
        installed_runtimes: set[str],
        available_backends: set[str] | None = None,
        allow_cloud: bool = False,
        commercial_required: bool = True,
    ) -> EngineSelection:
        available = available_backends or {
            "cpu",
            "cuda",
            "directml",
            "windowsml",
            "openvino",
            "vulkan",
            "cloud",
        }
        rejected: dict[str, str] = {}
        accepted: list[tuple[float, EngineCandidate, str]] = []
        for candidate in candidates:
            descriptor = self._descriptors.get(candidate.engine_id)
            if descriptor is None:
                rejected[candidate.id] = "ENGINE_NOT_REGISTERED"
                continue
            if route not in descriptor.routes:
                rejected[candidate.id] = "ROUTE_UNSUPPORTED"
                continue
            if descriptor.runtime not in installed_runtimes:
                rejected[candidate.id] = "RUNTIME_UNAVAILABLE"
                continue
            if descriptor.cloud and not allow_cloud:
                rejected[candidate.id] = "CLOUD_CONSENT_REQUIRED"
                continue
            if commercial_required and not descriptor.commercial_use:
                rejected[candidate.id] = "NON_COMMERCIAL"
                continue
            resource = (
                self.resource_governor.evaluate(
                    RuntimeFootprint(
                        process_mb=candidate.total_product_mb,
                        dedicated_vram_mb=candidate.vram_mb,
                    )
                )
                if candidate.total_product_mb > 0
                else self.resource_governor.preflight_model(
                    model_ram_mb=candidate.ram_mb,
                    shared_gpu_mb=candidate.shared_gpu_mb,
                    dedicated_vram_mb=candidate.vram_mb,
                )
            )
            if not resource.allowed:
                rejected[candidate.id] = resource.reason
                continue
            requested_backends = candidate.backends or (
                ("cloud",) if descriptor.cloud else ("cpu",)
            )
            backend = next(
                (item for item in requested_backends if item in available), None
            )
            if backend is None:
                rejected[candidate.id] = "BACKEND_UNAVAILABLE"
                continue
            score = self._score(candidate)
            if not math.isfinite(score):
                rejected[candidate.id] = "BENCHMARK_UNSTABLE"
                continue
            accepted.append((score, candidate, backend))
        if not accepted:
            raise RuntimeError("No existe un motor compatible con esta ruta y equipo")
        score, candidate, backend = max(
            accepted,
            key=lambda item: (
                item[0],
                -item[1].benchmark.p95_ms,
                item[1].id,
            ),
        )
        return EngineSelection(
            candidate=candidate,
            backend=backend,
            score=score,
            rejected=rejected,
        )
