"""Pruebas TDD para repartir CPU sin sobresuscribir el equipo."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from mily_ai.cpu_budget import detect_cpu_budget


class CpuBudgetTests(unittest.TestCase):
    def test_balanced_never_oversubscribes_physical_cores(self):
        for cores in range(1, 17):
            with self.subTest(cores=cores):
                budget = detect_cpu_budget("balanced", physical_cores=cores)
                if budget.parallel_stages:
                    self.assertLessEqual(
                        budget.asr_threads + budget.translation_threads,
                        cores,
                    )
                self.assertGreaterEqual(budget.asr_threads, 1)
                self.assertGreaterEqual(budget.translation_threads, 1)

    def test_single_core_disables_parallel_compute_stages(self):
        budget = detect_cpu_budget("balanced", physical_cores=1)
        self.assertFalse(budget.parallel_stages)
        self.assertEqual(budget.asr_threads, 1)
        self.assertEqual(budget.translation_threads, 1)

    def test_dual_core_balanced_reuses_both_cores_without_parallel_overlap(self):
        """Un Haswell 2C/4T debe reutilizar ambos cores en ASR y MT serial."""

        budget = detect_cpu_budget("balanced", physical_cores=2)
        self.assertFalse(budget.parallel_stages)
        self.assertEqual(budget.asr_threads, 2)
        self.assertEqual(budget.translation_threads, 2)

    def test_environment_physical_core_override_precedes_fallback_heuristic(self):
        """Rust pasa la topología real al sidecar mediante MILY_PHYSICAL_CPUS."""

        with patch.dict(os.environ, {"MILY_PHYSICAL_CPUS": "6"}, clear=False):
            budget = detect_cpu_budget("balanced")
        self.assertEqual(budget.physical_cores, 6)

    def test_invalid_environment_override_is_ignored(self):
        with patch.dict(os.environ, {"MILY_PHYSICAL_CPUS": "not-a-number"}, clear=False):
            budget = detect_cpu_budget("balanced", physical_cores=4)
        self.assertEqual(budget.physical_cores, 4)

    def test_light_profile_caps_compute_threads(self):
        budget = detect_cpu_budget("light", physical_cores=12)
        self.assertLessEqual(budget.asr_threads + budget.translation_threads, 2)

    def test_max_profile_uses_available_budget_without_overflow(self):
        budget = detect_cpu_budget("max", physical_cores=8)
        self.assertTrue(budget.parallel_stages)
        self.assertLessEqual(budget.asr_threads + budget.translation_threads, 8)
        self.assertGreaterEqual(budget.asr_threads, budget.translation_threads)


if __name__ == "__main__":
    unittest.main()
