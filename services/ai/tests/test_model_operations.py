import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.model_operations import _download_moonshine_fast_pack
from mily_ai.models import InstalledPack, ModelCatalog


class FakeInstaller:
    def __init__(self, lite_pack: InstalledPack):
        self.lite_pack = lite_pack
        self.install_calls = []
        self.verify_calls = []

    def install(self, pack_id: str) -> InstalledPack:
        self.install_calls.append(pack_id)
        if pack_id != "lite-en-es":
            raise AssertionError(f"pack inesperado: {pack_id}")
        return self.lite_pack

    def verify(self, pack_id: str, version: str) -> bool:
        self.verify_calls.append((pack_id, version))
        return True


class MoonshinePackTests(unittest.TestCase):
    def test_fast_pack_uses_streaming_assets_and_reuses_lite_translation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog_file = root / "catalog.json"
            catalog_file.write_text(
                json.dumps(
                    {
                        "schemaVersion": 2,
                        "packs": [
                            {
                                "schemaVersion": 2,
                                "id": "fast-moonshine-en-es",
                                "version": "1.0.0",
                                "title": "Fast",
                                "commercialUse": True,
                                "components": {
                                    "asr": {"provider": "moonshine"},
                                    "translation": {
                                        "provider": "marian-ct2",
                                        "sourceLanguage": "en",
                                        "targetLanguage": "es",
                                    },
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            catalog = ModelCatalog(root / "models", catalog_file)

            model_source = root / "moonshine-source"
            model_source.mkdir()
            for name in ("encoder_model.ort", "decoder_model_merged.ort", "tokenizer.bin"):
                (model_source / name).write_bytes(name.encode("ascii"))

            lite_root = root / "lite"
            translation = lite_root / "components" / "translation"
            translation.mkdir(parents=True)
            (translation / "model.bin").write_bytes(b"mt")
            (translation / "config.json").write_text("{}", encoding="utf-8")
            (translation / "source.spm").write_bytes(b"src")
            (translation / "target.spm").write_bytes(b"dst")
            lite = InstalledPack(
                id="lite-en-es",
                version="1.0.0",
                path=lite_root,
                active=False,
                title="Lite",
                commercial_use=True,
            )
            installer = FakeInstaller(lite)

            class ModelArch:
                TINY_STREAMING = 2

            calls = []

            def get_model_for_language(language, arch):
                calls.append((language, arch))
                return str(model_source), 2

            fake_moonshine = types.SimpleNamespace(
                ModelArch=ModelArch,
                get_model_for_language=get_model_for_language,
            )
            with patch.dict(sys.modules, {"moonshine_voice": fake_moonshine}):
                pack = _download_moonshine_fast_pack(installer, catalog)

            self.assertEqual(calls, [("en", 2)])
            self.assertEqual(installer.install_calls, ["lite-en-es"])
            self.assertTrue((pack.path / "components" / "asr" / "encoder_model.ort").is_file())
            self.assertTrue((pack.path / "components" / "translation" / "model.bin").is_file())
            config = json.loads(
                (pack.path / "components" / "asr" / "moonshine-config.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(config["modelArch"], 2)
            self.assertEqual(config["language"], "en")
            self.assertTrue((pack.path / "pack.json").is_file())


if __name__ == "__main__":
    unittest.main()
