import math
import unittest

from mily_ai.benchmarking import performance_gate, summarize_latencies


class BenchmarkingTests(unittest.TestCase):
    def test_summary_reports_interpolated_p50_and_p95(self):
        summary = summarize_latencies([100.0, 200.0, 300.0, 400.0, 500.0])
        self.assertEqual(summary["count"], 5)
        self.assertAlmostEqual(summary["p50Ms"], 300.0, places=3)
        self.assertAlmostEqual(summary["p95Ms"], 480.0, places=3)
        self.assertAlmostEqual(summary["meanMs"], 300.0, places=3)
        self.assertEqual(summary["minMs"], 100.0)
        self.assertEqual(summary["maxMs"], 500.0)

    def test_summary_rejects_empty_or_non_finite_samples(self):
        with self.assertRaises(ValueError):
            summarize_latencies([])
        with self.assertRaises(ValueError):
            summarize_latencies([10.0, math.inf])
        with self.assertRaises(ValueError):
            summarize_latencies([10.0, math.nan])

    def test_performance_gate_requires_rtf_and_mt_p95_under_limits(self):
        passed = performance_gate(
            asr_rtf_p95=0.78,
            mt_p95_ms=420.0,
            max_asr_rtf_p95=1.50,
            max_mt_p95_ms=2000.0,
        )
        self.assertTrue(passed["passed"])
        self.assertEqual(passed["failures"], [])

        failed = performance_gate(
            asr_rtf_p95=1.80,
            mt_p95_ms=2400.0,
            max_asr_rtf_p95=1.50,
            max_mt_p95_ms=2000.0,
        )
        self.assertFalse(failed["passed"])
        self.assertIn("ASR_RTF_P95", failed["failures"])
        self.assertIn("MT_P95", failed["failures"])

    def test_performance_gate_rejects_non_finite_metrics(self):
        gate = performance_gate(
            asr_rtf_p95=math.nan,
            mt_p95_ms=400.0,
            max_asr_rtf_p95=1.50,
            max_mt_p95_ms=2000.0,
        )
        self.assertFalse(gate["passed"])
        self.assertIn("ASR_RTF_P95_INVALID", gate["failures"])


if __name__ == "__main__":
    unittest.main()
