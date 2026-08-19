import unittest
from mily_ai.onnx_lab import OnnxCandidateMetrics, accept_optimized_candidate


class OnnxLabTests(unittest.TestCase):
    def test_candidate_must_gain_without_quality_regression(self):
        base = OnnxCandidateMetrics("fp32", 400, 430, 1.0)
        self.assertTrue(accept_optimized_candidate(base, OnnxCandidateMetrics("int8", 360, 400, 0.995)))
        self.assertFalse(accept_optimized_candidate(base, OnnxCandidateMetrics("bad", 300, 350, 0.97)))
        self.assertFalse(accept_optimized_candidate(base, OnnxCandidateMetrics("same", 398, 425, 1.0)))


if __name__ == "__main__":
    unittest.main()
