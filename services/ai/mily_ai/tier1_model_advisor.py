"""ModelAdvisor 2.1 con benchmark de las cuatro rutas Tier 1."""

from __future__ import annotations

from .model_advisor import ModelAdvisor
from .tier1_engine_benchmark import benchmark_installed_pack


class Tier1ModelAdvisor(ModelAdvisor):
    def __init__(
        self,
        catalog,
        installer,
        *,
        governor=None,
        inventory=None,
        benchmarker=None,
    ):
        super().__init__(
            catalog,
            installer,
            governor=governor,
            inventory=inventory,
            benchmarker=benchmarker or benchmark_installed_pack,
        )
