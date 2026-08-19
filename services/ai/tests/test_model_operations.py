import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.model_operations import _download_moonshine_fast_pack
from mily_ai.models import InstalledPack, ModelCatalog


# Dependencias STT declaradas por el catálogo oficial de Moonshine para una
# arquitectura streaming. Los recursos de spelling se descargan por separado y
# no son necesarios mientras MilyVoice no active MOONSHINE_FLAG_SPELLING_MODE.
MOONSHINE_010_REQUIRED_STREAMING_ASSETS = (
    "adapter.ort",
    "cross_kv.ort",
    "decoder_kv.ort",
    "encoder.ort",
    "frontend.ort",
    "streaming_config.json",
    "tokenizer.bin",
)
MOONSHINE_010_OPTIONAL_SPELLING_ASSETS = (
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

    @staticmethod
    def _write_required_streaming_assets(model_source: Path) -> None:
        for name in MOONSHINE_010_REQUIRED_STREAMING_ASSETS:
            payload = b"{}" if name.endswith(".json") else name.encode("ascii")
            (model_source / name).write_bytes(payload)

    def _download(self, root: Path, model_source: Path):
        catalog = self._catalog(root)
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
        return pack, installer, calls

    def test_fast_pack_accepts_official_stt_layout_without_spelling_assets(self):
        """El spelling es opcional y no puede bloquear ASR/translación normal."""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_source = root / "moonshine-source"
            model_source.mkdir()
            self._write_required_streaming_assets(model_source)

            pack, installer, calls = self._download(root, model_source)

            self.assertEqual(calls, [("en", 2)])
            self.assertEqual(installer.install_calls, ["lite-en-es"])
            for name in MOONSHINE_010_REQUIRED_STREAMING_ASSETS:
                with self.subTest(name=name):
                    self.assertTrue((pack.path / "components" / "asr" / name).is_file())
            for name in MOONSHINE_010_OPTIONAL_SPELLING_ASSETS:
                with self.subTest(optional=name):
                    self.assertFalse((pack.path / "components" / "asr" / name).exists())
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

    def test_fast_pack_ignores_empty_optional_spelling_metadata(self):
        """Moonshine puede entregar spelling por separado; no se usa en este pack."""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_source = root / "moonshine-source"
            model_source.mkdir()
            self._write_required_streaming_assets(model_source)
            (model_source / "spelling_cnn.ort").write_bytes(b"optional")
            (model_source / "spelling_cnn_meta.json").write_bytes(b"")

            pack, _installer, _calls = self._download(root, model_source)

            self.assertTrue((pack.path / "components" / "asr" / "frontend.ort").is_file())
            # Se conservan si el proveedor los entregó, pero no participan en el
            # readiness del ASR ni se activa spelling mode.
            self.assertTrue(
                (pack.path / "components" / "asr" / "spelling_cnn.ort").is_file()
            )

    def test_fast_pack_rejects_streaming_layout_missing_decoder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = self._catalog(root)
            model_source = root / "moonshine-source"
            model_source.mkdir()
            self._write_required_streaming_assets(model_source)
            (model_source / "decoder_kv.ort").unlink()

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

    def test_fast_pack_rejects_empty_required_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = self._catalog(root)
            model_source = root / "moonshine-source"
            model_source.mkdir()
            self._write_required_streaming_assets(model_source)
            (model_source / "encoder.ort").write_bytes(b"")

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
