"""Política de laboratorio para optimizar Moonshine sin degradarlo a ciegas."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OnnxCandidateMetrics:
    name: str
    p95_ms: float
    peak_mb: float
    quality_ratio: float


def accept_optimized_candidate(baseline: OnnxCandidateMetrics, candidate: OnnxCandidateMetrics) -> bool:
    """Solo promueve ORT optimizado/INT8 si gana y conserva >=99% de calidad."""
    if candidate.quality_ratio < 0.99:
        return False
    latency_gain = candidate.p95_ms <= baseline.p95_ms * 0.95
    memory_gain = candidate.peak_mb <= baseline.peak_mb * 0.90
    no_material_regression = candidate.p95_ms <= baseline.p95_ms * 1.03
    return (latency_gain or memory_gain) and no_material_regression
