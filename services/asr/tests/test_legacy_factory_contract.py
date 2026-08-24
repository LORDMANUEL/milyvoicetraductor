import inspect
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


class LegacyFactoryContractTests(unittest.TestCase):
    def test_importing_mily_asr_does_not_import_legacy_provider_factory(self):
        code = (
            "import sys; import mily_asr; "
            "assert 'mily_ai.provider_factory' not in sys.modules; "
            "assert 'mily_ai.providers' not in sys.modules"
        )
        subprocess.run(
            [sys.executable, "-c", code],
            env=dict(os.environ),
            check=True,
            capture_output=True,
            text=True,
        )

    def test_current_factory_exposes_promoted_asr_provider_ids_and_signature(self):
        from mily_ai import provider_factory

        self.assertTrue(
            {"faster-whisper", "moonshine", "sherpa-onnx"}.issubset(
                set(provider_factory.ASR_BUILDERS)
            )
        )
        parameters = list(inspect.signature(provider_factory.build_asr_provider).parameters)
        self.assertEqual(
            parameters,
            ["component", "model_path", "compute_profile", "cpu_budget", "word_timestamps"],
        )

    def test_promoted_lite_packs_are_two_gb_class_and_map_to_expected_providers(self):
        root = Path(__file__).resolve().parents[3]
        payload = json.loads(
            (root / "services/ai/mily_ai/model-packs.json").read_text(encoding="utf-8")
        )
        packs = {pack["id"]: pack for pack in payload["packs"]}
        expected = {
            "fast-moonshine-en-es": ("moonshine", 430),
            "lite-en-es": ("faster-whisper", 360),
            "sherpa-zipformer-en-es": ("sherpa-onnx", 150),
        }

        for pack_id, (provider, max_asr_mb) in expected.items():
            with self.subTest(pack=pack_id):
                pack = packs[pack_id]
                self.assertEqual(pack["tier"], "lite")
                self.assertEqual(pack["recommendedRamGb"], 2)
                self.assertLessEqual(pack["ramMb"], 1200)
                self.assertEqual(pack["components"]["asr"]["provider"], provider)
                self.assertLessEqual(pack["components"]["asr"]["estimatedRamMb"], max_asr_mb)


if __name__ == "__main__":
    unittest.main()
