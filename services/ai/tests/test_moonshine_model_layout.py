import tempfile
import unittest
from pathlib import Path

from mily_ai.model_operations import (
    _copy_moonshine_model_assets,
    _moonshine_required_files,
)
from mily_ai.models import ModelOperationError


class FakeArch:
    def __init__(self, name: str, value: int):
        self.name = name
        self.value = value

    def __int__(self) -> int:
        return self.value


class MoonshineModelLayoutTests(unittest.TestCase):
    STREAMING_REQUIRED = {
        "adapter.ort",
        "cross_kv.ort",
        "decoder_kv.ort",
        "encoder.ort",
        "frontend.ort",
        "streaming_config.json",
        "tokenizer.bin",
    }
    STREAMING_ATTENTION = "decoder_kv_with_attention.ort"
    NON_STREAMING_REQUIRED = {
        "encoder_model.ort",
        "decoder_model_merged.ort",
        "tokenizer.bin",
    }

    def test_tiny_streaming_uses_the_current_official_layout(self):
        required = set(_moonshine_required_files(FakeArch("TINY_STREAMING", 2)))
        self.assertEqual(required, self.STREAMING_REQUIRED)

    def test_word_timestamps_add_only_the_streaming_attention_decoder(self):
        required = set(
            _moonshine_required_files(
                FakeArch("TINY_STREAMING", 2),
                include_word_timestamps=True,
            )
        )
        self.assertEqual(
            required,
            self.STREAMING_REQUIRED | {self.STREAMING_ATTENTION},
        )

    def test_non_streaming_arch_keeps_the_legacy_three_file_layout(self):
        required = set(_moonshine_required_files(FakeArch("TINY", 0)))
        self.assertEqual(required, self.NON_STREAMING_REQUIRED)

    def test_copy_keeps_only_runtime_assets_and_drops_optional_spelling_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            expected = self.STREAMING_REQUIRED | {self.STREAMING_ATTENTION}
            for name in expected:
                (source / name).write_bytes(name.encode("utf-8"))
            (source / "spelling_cnn.ort").write_bytes(b"optional")
            (source / "spelling_cnn_meta.json").write_text("{}", encoding="utf-8")

            copied = _copy_moonshine_model_assets(
                source,
                target,
                FakeArch("TINY_STREAMING", 2),
                include_word_timestamps=True,
            )

            self.assertEqual(set(copied), expected)
            self.assertEqual(
                {path.name for path in target.iterdir()},
                expected,
            )
            self.assertFalse((target / "spelling_cnn.ort").exists())

    def test_missing_streaming_asset_is_rejected_before_pack_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            target = root / "target"
            source.mkdir()
            for name in self.STREAMING_REQUIRED - {"decoder_kv.ort"}:
                (source / name).write_bytes(b"fixture")

            with self.assertRaises(ModelOperationError) as raised:
                _copy_moonshine_model_assets(
                    source,
                    target,
                    FakeArch("TINY_STREAMING", 2),
                )

            self.assertEqual(raised.exception.code, "MODEL_PROVIDER_ERROR")
            self.assertIn("decoder_kv.ort", raised.exception.message)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
