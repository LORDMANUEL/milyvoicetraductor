import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.model_operations import _download_sherpa_zh_pack
from mily_ai.models import InstalledPack, ModelCatalog


class _Installer:
    def __init__(self):
        self.verify_calls = []

    def verify(self, pack_id: str, version: str) -> bool:
        self.verify_calls.append((pack_id, version))
        return True


class BetaAlphaSherpaInstallTests(unittest.TestCase):
    def test_zipformer_zh_pack_downloads_only_pinned_int8_assets_and_reuses_teacher_mt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = ModelCatalog(root / "models")
            teacher_root = root / "teacher"
            teacher_mt = teacher_root / "components" / "translation"
            for index in (1, 2):
                stage = teacher_mt / f"stage-{index}"
                stage.mkdir(parents=True, exist_ok=True)
                (stage / "model.bin").write_bytes(b"model")
                (stage / "config.json").write_text("{}", encoding="utf-8")
                (stage / "source.spm").write_bytes(b"source")
                (stage / "target.spm").write_bytes(b"target")
            teacher = InstalledPack(
                id="lite-zh-es",
                version="1.0.0",
                path=teacher_root,
                active=False,
                title="teacher",
                commercial_use=True,
            )
            calls = []

            def snapshot_download(**kwargs):
                calls.append(kwargs)
                target = Path(kwargs["local_dir"])
                target.mkdir(parents=True, exist_ok=True)
                for name in kwargs["allow_patterns"]:
                    if "*" in name:
                        continue
                    path = target / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"asset")
                return str(target)

            fake_hf = types.SimpleNamespace(snapshot_download=snapshot_download)
            installer = _Installer()
            with patch.dict(sys.modules, {"huggingface_hub": fake_hf}), patch(
                "mily_ai.model_operations._download_lite_zh_es_pack",
                return_value=teacher,
            ):
                pack = _download_sherpa_zh_pack(
                    installer, catalog, "betaalpha-zipformer-zh-es"
                )

            definition = catalog.definition("betaalpha-zipformer-zh-es")
            asr = definition["components"]["asr"]
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["repo_id"], asr["repoId"])
            self.assertEqual(calls[0]["revision"], asr["revision"])
            self.assertEqual(calls[0]["allow_patterns"], asr["allowPatterns"])
            asr_root = pack.path / "components" / "asr"
            self.assertTrue((asr_root / asr["encoder"]).is_file())
            self.assertTrue((asr_root / asr["decoder"]).is_file())
            self.assertTrue((asr_root / asr["joiner"]).is_file())
            self.assertTrue((asr_root / asr["tokens"]).is_file())
            self.assertTrue(
                (pack.path / "components" / "translation" / "stage-1" / "model.bin").is_file()
            )
            self.assertTrue((pack.path / "pack.json").is_file())
            self.assertIn((pack.id, pack.version), installer.verify_calls)

    def test_paraformer_pack_requires_only_encoder_decoder_and_tokens(self):
        definition = ModelCatalog(Path("unused")).definition(
            "betaalpha-paraformer-zh-es"
        )
        asr = definition["components"]["asr"]
        self.assertEqual(asr["sherpaMode"], "online-paraformer")
        self.assertEqual(
            set(asr["allowPatterns"]),
            {"encoder.int8.onnx", "decoder.int8.onnx", "tokens.txt"},
        )
        self.assertNotIn("joiner", asr)


if __name__ == "__main__":
    unittest.main()
