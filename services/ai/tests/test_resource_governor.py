import unittest

from mily_ai.resource_governor import ResourceGovernor, ResourceLimits, RuntimeFootprint


class ResourceGovernorTests(unittest.TestCase):
    def setUp(self):
        self.governor = ResourceGovernor(ResourceLimits())

    def test_process_over_two_gib_is_rejected(self):
        decision = self.governor.evaluate(RuntimeFootprint(process_mb=2050))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "PROCESS_MEMORY_LIMIT")

    def test_integrated_gpu_shared_memory_counts_against_process_budget(self):
        decision = self.governor.evaluate(
            RuntimeFootprint(process_mb=1750, shared_gpu_mb=320)
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.effective_process_mb, 2070)

    def test_512mb_gpu_uses_only_384mb_budget(self):
        decision = self.governor.evaluate(
            RuntimeFootprint(process_mb=900, dedicated_vram_mb=385)
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "VRAM_LIMIT")

    def test_mode_is_selected_from_effective_working_set(self):
        self.assertEqual(
            self.governor.evaluate(RuntimeFootprint(process_mb=650)).mode,
            "rescue",
        )
        self.assertEqual(
            self.governor.evaluate(RuntimeFootprint(process_mb=1100)).mode,
            "lite",
        )
        self.assertEqual(
            self.governor.evaluate(RuntimeFootprint(process_mb=1450)).mode,
            "balanced",
        )

    def test_model_load_is_checked_before_allocation(self):
        decision = self.governor.can_load(
            current_process_mb=980,
            model_ram_mb=740,
            shared_gpu_mb=0,
            dedicated_vram_mb=0,
        )
        self.assertTrue(decision.allowed)
        rejected = self.governor.can_load(
            current_process_mb=1500,
            model_ram_mb=600,
            shared_gpu_mb=0,
            dedicated_vram_mb=0,
        )
        self.assertFalse(rejected.allowed)


if __name__ == "__main__":
    unittest.main()
