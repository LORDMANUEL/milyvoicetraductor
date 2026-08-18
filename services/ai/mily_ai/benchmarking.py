"""Métricas deterministas y gates reutilizables por MegaBench.

Este módulo no realiza inferencia ni I/O. Recibe mediciones locales ya tomadas y
produce estadísticas JSON-serializables para CI, diagnóstico y promoción de
backends/modelos.
"""
from __future__ import annotations

import math
from statistics import fmean
from typing import Iterable


def _finite_samples(values: Iterable[float]) -> list[float]:
    samples = [float(value) for value in values]
    if not samples:
        raise ValueError("MegaBench requiere al menos una muestra")
    if any(not math.isfinite(value) or value < 0.0 for value in samples):
        raise ValueError("MegaBench solo acepta muestras finitas y no negativas")
    return sorted(samples)


def percentile(values: Iterable[float], percentile_value: float) -> float:
    """Percentil con interpolación lineal equivalente al método inclusivo común."""
    samples = _finite_samples(values)
    percentile_value = float(percentile_value)
    if not 0.0 <= percentile_value <= 100.0 or not math.isfinite(percentile_value):
        raise ValueError("Percentil fuera de rango")
    if len(samples) == 1:
        return samples[0]
    position = (len(samples) - 1) * (percentile_value / 100.0)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return samples[lower]
    weight = position - lower
    return samples[lower] * (1.0 - weight) + samples[upper] * weight


def summarize_latencies(values: Iterable[float]) -> dict[str, float | int]:
    """Resumen compacto usado por los reportes de latencia de MilyVoice."""
    samples = _finite_samples(values)
    return {
        "count": len(samples),
        "p50Ms": round(percentile(samples, 50.0), 3),
        "p95Ms": round(percentile(samples, 95.0), 3),
        "meanMs": round(fmean(samples), 3),
        "minMs": round(samples[0], 3),
        "maxMs": round(samples[-1], 3),
    }


def performance_gate(
    *,
    asr_rtf_p95: float,
    mt_p95_ms: float,
    max_asr_rtf_p95: float,
    max_mt_p95_ms: float,
) -> dict[str, object]:
    """Evalúa límites de regresión sin confundirlos con hardware físico objetivo."""
    failures: list[str] = []
    metrics = {
        "asrRtfP95": float(asr_rtf_p95),
        "mtP95Ms": float(mt_p95_ms),
        "maxAsrRtfP95": float(max_asr_rtf_p95),
        "maxMtP95Ms": float(max_mt_p95_ms),
    }

    if not math.isfinite(metrics["asrRtfP95"]):
        failures.append("ASR_RTF_P95_INVALID")
    elif metrics["asrRtfP95"] > metrics["maxAsrRtfP95"]:
        failures.append("ASR_RTF_P95")

    if not math.isfinite(metrics["mtP95Ms"]):
        failures.append("MT_P95_INVALID")
    elif metrics["mtP95Ms"] > metrics["maxMtP95Ms"]:
        failures.append("MT_P95")

    return {"passed": not failures, "failures": failures, "metrics": metrics}
