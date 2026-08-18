import unittest

from mily_ai.compute_router import BackendLoadError, load_backend_with_fallback


class ComputeRouterTests(unittest.TestCase):
    def test_auto_prefers_cuda_when_cuda_loads(self):
        calls = []

        def loader(device):
            calls.append(device)
            return f"model:{device}"

        result = load_backend_with_fallback("auto", 1, loader)
        self.assertEqual(result.device, "cuda")
        self.assertEqual(result.value, "model:cuda")
        self.assertFalse(result.fallback_used)
        self.assertEqual(calls, ["cuda"])

    def test_auto_falls_back_to_cpu_when_cuda_initialization_fails(self):
        calls = []

        def loader(device):
            calls.append(device)
            if device == "cuda":
                raise RuntimeError("driver mismatch")
            return "model:cpu"

        result = load_backend_with_fallback("auto", 1, loader)
        self.assertEqual(result.device, "cpu")
        self.assertEqual(result.value, "model:cpu")
        self.assertTrue(result.fallback_used)
        self.assertEqual(calls, ["cuda", "cpu"])
        self.assertIn("RuntimeError", result.reason)

    def test_cpu_profile_never_touches_cuda(self):
        calls = []

        def loader(device):
            calls.append(device)
            return device

        result = load_backend_with_fallback("cpu", 4, loader)
        self.assertEqual(result.device, "cpu")
        self.assertEqual(calls, ["cpu"])

    def test_forced_gpu_fails_clearly_when_cuda_is_missing(self):
        with self.assertRaises(BackendLoadError) as context:
            load_backend_with_fallback("gpu", 0, lambda _device: object())
        self.assertEqual(context.exception.code, "CUDA_UNAVAILABLE")

    def test_forced_gpu_does_not_hide_cuda_initialization_failure(self):
        def loader(_device):
            raise OSError("cuda dll failure")

        with self.assertRaises(BackendLoadError) as context:
            load_backend_with_fallback("gpu", 1, loader)
        self.assertEqual(context.exception.code, "CUDA_INIT_FAILED")


if __name__ == "__main__":
    unittest.main()
