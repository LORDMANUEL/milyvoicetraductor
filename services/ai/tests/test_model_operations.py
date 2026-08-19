import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.model_operations import _download_moonshine_fast_pack
from mily_ai.models import InstalledPack, ModelCatalog


MOONSHINE_010_STREAMING_ASSETS = (
    "adapter.ort",
    "cross_kv.ort",
    "decoder_kv.ort",
    "encoder.ort",
    "frontend.ort",
    "streaming_config.json",
    "tokenizer.bin",
    "spelling_cnn.ort",
    "spelling_cnn_meta.json",
)


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
    def _catalog(self, root: Path) -> ModelCatalog:
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
        return ModelCatalog(root / "models", catalog_file)

    def _lite_pack(self, root: Path) -> InstalledPack:
        lite_root = root / "lite"
        translation = lite_root / "components" / "translation"
        translation.mkdir(parents=True)
        (translation / "model.bin").write_bytes(b"mt")
        (translation / "config.json").write_text("{}", encoding="utf-8")
        (translation / "source.spm").write_bytes(b"src")
        (translation / "target.spm").write_bytes(b"dst")
        return InstalledPack(
            id="lite-en-es",
            version="1.0.0",
            path=lite_root,
            active=False,
            title="Lite",
            commercial_use=True,
        )

    def test_fast_pack_accepts_official_moonshine_010_streaming_layout(self):
        """Regresión del layout descargado realmente por moonshine-voice 0.1.0."""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = self._catalog(root)
            model_source = root / "moonshine-source"
            model_source.mkdir()
            for name in MOONSHINE_010_STREAMING_ASSETS:
                payload = b"{}" if name.endswith(".json") else name.encode("ascii")
                (model_source / name).write_bytes(payload)

            installer = FakeInstaller(self._lite_pack(root))

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
            for name in MOONSHINE_010_STREAMING_ASSETS:
                with self.subTest(name=name):
                    self.assertTrue((pack.path / "components" / "asr" / name).is_file())
            self.assertTrue(
                (pack.path / "components" / "translation" / "model.bin").is_file()
            )
            config = json.loads(
                (pack.path / "components" / "asr" / "moonshine-config.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(config["modelArch"], 2)
            self.assertEqual(config["language"], "en")
            self.assertTrue((pack.path / "pack.json").is_file())

    def test_fast_pack_rejects_streaming_layout_missing_decoder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = self._catalog(root)
            model_source = root / "moonshine-source"
            model_source.mkdir()
            for name in MOONSHINE_010_STREAMING_ASSETS:
                if name == "decoder_kv.ort":
                    continue
                payload = b"{}" if name.endswith(".json") else name.encode("ascii")
                (model_source / name).write_bytes(payload)

            installer = FakeInstaller(self._lite_pack(root))

            class ModelArch:
                TINY_STREAMING = 2

            fake_moonshine = types.SimpleNamespace(
                ModelArch=ModelArch,
                get_model_for_language=lambda *_args: (str(model_source), 2),
            )
            with patch.dict(sys.modules, {"moonshine_voice": fake_moonshine}):
                with self.assertRaisesRegex(Exception, "incompleto"):
                    _download_moonshine_fast_pack(installer, catalog)


if __name__ == "__main__":
    unittest.main()
