import unittest
from mily_ai.model_lab import StudentMetrics, evaluate_zh_es_student


class ModelLabBetaAlphaTests(unittest.TestCase):
    def test_student_requires_quality_latency_memory_and_sample_floor(self):
        good = StudentMetrics(quality_ratio=0.98, p95_ms=180, peak_mb=820, samples=300)
        self.assertTrue(evaluate_zh_es_student(good).promote)
        self.assertEqual(evaluate_zh_es_student(StudentMetrics(0.95, 180, 820, 300)).reason, "QUALITY_REGRESSION")
        self.assertEqual(evaluate_zh_es_student(StudentMetrics(0.98, 250, 820, 300)).reason, "LATENCY_REGRESSION")
        self.assertEqual(evaluate_zh_es_student(StudentMetrics(0.98, 180, 950, 300)).reason, "MEMORY_REGRESSION")
        self.assertEqual(evaluate_zh_es_student(StudentMetrics(0.98, 180, 820, 50)).reason, "INSUFFICIENT_EVAL_SAMPLES")


if __name__ == "__main__":
    unittest.main()
