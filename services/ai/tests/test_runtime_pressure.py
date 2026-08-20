import unittest

from mily_ai.telemetry import LatencyController


class RuntimePressureRecoveryTests(unittest.TestCase):
    def test_escalation_is_immediate_but_recovery_requires_stability(self):
        controller = LatencyController(
            memory_provider=lambda: 0.0,
            product_reserve_mb=0.0,
            recovery_samples=3,
        )
        self.assertEqual(
            controller.classify(
                2600,
                8,
                1.9,
                translation_queue_age_ms=2600,
                process_memory_mb=1980,
            ),
            "rescue",
        )
        for _ in range(2):
            self.assertEqual(
                controller.classify(
                    0,
                    0,
                    0.1,
                    translation_queue_age_ms=0,
                    process_memory_mb=700,
                ),
                "rescue",
            )
        self.assertEqual(
            controller.classify(
                0,
                0,
                0.1,
                translation_queue_age_ms=0,
                process_memory_mb=700,
            ),
            "catch_up",
        )

    def test_recovery_steps_down_one_level_at_a_time(self):
        controller = LatencyController(
            memory_provider=lambda: 0.0,
            product_reserve_mb=0.0,
            recovery_samples=2,
        )
        controller.classify(2500, 8, 2.0, process_memory_mb=1980)
        expected = ["rescue", "catch_up", "catch_up", "pressure", "pressure", "healthy"]
        observed = [
            controller.classify(0, 0, 0.1, process_memory_mb=600)
            for _ in expected
        ]
        self.assertEqual(observed, expected)

    def test_new_pressure_resets_recovery_counter(self):
        controller = LatencyController(
            memory_provider=lambda: 0.0,
            product_reserve_mb=0.0,
            recovery_samples=3,
        )
        controller.classify(1300, 6, 1.4, process_memory_mb=1700)
        self.assertEqual(controller.state, "catch_up")
        controller.classify(0, 0, 0.1, process_memory_mb=600)
        controller.classify(0, 0, 0.1, process_memory_mb=600)
        self.assertEqual(
            controller.classify(700, 3, 0.9, process_memory_mb=1300),
            "catch_up",
        )
        for _ in range(2):
            self.assertEqual(
                controller.classify(0, 0, 0.1, process_memory_mb=600),
                "catch_up",
            )


if __name__ == "__main__":
    unittest.main()
