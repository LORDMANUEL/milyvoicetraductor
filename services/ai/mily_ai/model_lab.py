"""Model Lab BetaAlpha: promoción segura de un estudiante directo ZH→ES.

No sustituye la cascada por una promesa: un estudiante solo puede ser candidato
Auto cuando demuestra calidad, memoria y latencia contra el teacher vigente.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StudentMetrics:
    quality_ratio: float
    p95_ms: float
    peak_mb: float
    samples: int


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    promote: bool
    reason: str


def evaluate_zh_es_student(metrics: StudentMetrics) -> PromotionDecision:
    if metrics.samples < 200:
        return PromotionDecision(False, "INSUFFICIENT_EVAL_SAMPLES")
    if metrics.quality_ratio < 0.97:
        return PromotionDecision(False, "QUALITY_REGRESSION")
    if metrics.p95_ms > 220:
        return PromotionDecision(False, "LATENCY_REGRESSION")
    if metrics.peak_mb > 900:
        return PromotionDecision(False, "MEMORY_REGRESSION")
    return PromotionDecision(True, "PROMOTION_GATE_PASSED")
