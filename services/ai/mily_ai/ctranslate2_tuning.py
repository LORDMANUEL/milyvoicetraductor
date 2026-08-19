"""Microbenchmark persistente de compute types CTranslate2 para BetaAlpha.

Se ejecuta únicamente para packs BetaAlpha que lo solicitan. El resultado queda
fuera del pack firmado para no invalidar hashes del Model Manager.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from .betaalpha_optimization import ComputeTypeSelector
from .cpu_budget import CpuBudget


@dataclass(frozen=True, slots=True)
class ComputeTuneResult:
    compute_type: str
    timings_ms: dict[str, float]
    cached: bool


TranslatorFactory = Callable[[str], object]
BenchmarkFn = Callable[[object, Sequence[str]], float]


class CTranslate2ComputeTuner:
    """Escoge el tipo de cuantización más rápido y lo recuerda por equipo/modelo."""

    def __init__(self, cache_path: Path | None = None):
        if cache_path is None:
            override = os.environ.get("MILY_BETAALPHA_COMPUTE_CACHE", "").strip()
            if override:
                cache_path = Path(override)
            else:
                local = os.environ.get("LOCALAPPDATA", "").strip()
                root = Path(local) if local else Path(tempfile.gettempdir())
                cache_path = root / "MilyVoiceTraductor" / "cache" / "betaalpha-compute.json"
        self.cache_path = Path(cache_path)
        self.selector = ComputeTypeSelector()

    @staticmethod
    def _model_signature(model_path: Path) -> str:
        model_path = Path(model_path)
        model_file = model_path / "model.bin"
        size = 0
        try:
            size = int(model_file.stat().st_size)
        except OSError:
            pass
        raw = "|".join(
            (
                str(model_path.resolve()),
                str(size),
                platform.machine(),
                platform.processor(),
            )
        )
        return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()

    @staticmethod
    def _cache_key(
        model_path: Path,
        source_language: str,
        supported: Iterable[str],
        budget: CpuBudget,
    ) -> str:
        raw = "|".join(
            (
                CTranslate2ComputeTuner._model_signature(model_path),
                str(source_language).lower(),
                ",".join(sorted(str(item) for item in supported)),
                str(budget.physical_cores),
                str(budget.translation_threads),
            )
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _read(self) -> dict:
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return {"schemaVersion": 1, "entries": {}}
        if not isinstance(payload, dict) or not isinstance(payload.get("entries"), dict):
            return {"schemaVersion": 1, "entries": {}}
        return payload

    def _write(self, payload: dict) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        temp.replace(self.cache_path)

    @staticmethod
    def _release(translator: object) -> None:
        unload = getattr(translator, "unload_model", None)
        if callable(unload):
            try:
                unload(to_cpu=False)
            except TypeError:
                unload()
            except Exception:
                pass

    def choose(
        self,
        *,
        model_path: Path,
        source_language: str,
        supported: set[str],
        budget: CpuBudget,
        translator_factory: TranslatorFactory,
        probe_tokens: Sequence[str],
        benchmark: BenchmarkFn,
    ) -> ComputeTuneResult:
        normalized_supported = {
            str(item).strip().lower() for item in supported if str(item).strip()
        }
        key = self._cache_key(
            model_path,
            source_language,
            normalized_supported,
            budget,
        )
        payload = self._read()
        entry = payload.get("entries", {}).get(key)
        if isinstance(entry, dict):
            compute_type = str(entry.get("computeType", "")).strip().lower()
            if compute_type in normalized_supported:
                timings = {
                    str(name): float(value)
                    for name, value in dict(entry.get("timingsMs", {})).items()
                    if isinstance(value, (int, float))
                    and math.isfinite(float(value))
                    and float(value) > 0
                }
                return ComputeTuneResult(compute_type, timings, True)

        timings: dict[str, float] = {}
        candidates = [
            item
            for item in self.selector.SAFE_ORDER
            if item in normalized_supported
        ]
        for compute_type in candidates:
            translator = None
            try:
                translator = translator_factory(compute_type)
                elapsed = float(benchmark(translator, probe_tokens))
                if math.isfinite(elapsed) and elapsed > 0:
                    timings[compute_type] = elapsed
            except Exception:
                continue
            finally:
                if translator is not None:
                    self._release(translator)

        selected = self.selector.choose(
            supported=normalized_supported,
            timings_ms=timings,
        )
        entries = payload.setdefault("entries", {})
        entries[key] = {
            "computeType": selected,
            "timingsMs": timings,
            "physicalCores": budget.physical_cores,
            "translationThreads": budget.translation_threads,
        }
        try:
            self._write(payload)
        except OSError:
            # La caché mejora arranques posteriores, pero nunca debe bloquear realtime.
            pass
        return ComputeTuneResult(selected, timings, False)
