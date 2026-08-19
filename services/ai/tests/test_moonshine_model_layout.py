import tempfile
import unittest
from pathlib import Path

from mily_ai.model_operations import (
    _MOONSHINE_010_REQUIRED_STREAMING_ASSETS,
    _moonshine_streaming_model_ready,
)


class MoonshineStreamingLayoutTests(unittest.TestCase):
    def _write_valid_layout(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        for name in _MOONSHINE_010_REQUIRED_STREAMING_ASSETS:
            target = root / name
            if name.endswith(".json"):
                target.write_text("{}", encoding="utf-8")
            else:
                target.write_bytes(b"milyvoice")

    def test_current_streaming_layout_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "moonshine"
            self._write_valid_layout(root)
            self.assertTrue(_moonshine_streaming_model_ready(root))

    def test_legacy_non_streaming_layout_does_not_mask_missing_streaming_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "moonshine"
            root.mkdir(parents=True)
            (root / "encoder_model.ort").write_bytes(b"legacy")
            (root / "decoder_model_merged.ort").write_bytes(b"legacy")
            (root / "tokenizer.bin").write_bytes(b"legacy")
            self.assertFalse(_moonshine_streaming_model_ready(root))

    def test_missing_streaming_decoder_is_rejected_before_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "moonshine"
            self._write_valid_layout(root)
            (root / "decoder_kv.ort").unlink()
            self.assertFalse(_moonshine_streaming_model_ready(root))

    def test_zero_length_binary_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "moonshine"
            self._write_valid_layout(root)
            (root / "encoder.ort").write_bytes(b"")
            self.assertFalse(_moonshine_streaming_model_ready(root))

    def test_optional_spelling_assets_are_not_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "moonshine"
            self._write_valid_layout(root)
            self.assertFalse((root / "spelling_cnn.ort").exists())
            self.assertTrue(_moonshine_streaming_model_ready(root))


if __name__ == "__main__":
    unittest.main()
