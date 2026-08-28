import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from mily_ai.tier1_model_operations import _download_lite_cascade_pack
from mily_ai.models import ModelCatalog


class FakeInstaller:
    def __init__(self):
        self.verify_calls = []

    def verify(self, pack_id: str, version: str) -> bool:
        self.verify_calls.append((pack_id, version))
        return True


class Tier1CascadeDownloadTests(unittest.TestCase):
    def _catalog(self, root: Path) -> ModelCatalog:
        catalog_file = root / "catalog.json"
        catalog_file.write_text(
            json.dumps(
                {
                    "schemaVersion": 2,
                    "packs": [
                        {
                            "schemaVersion": 2,
                            "id": "lite-es-zh",
                            "version": "1.0.0",
                            "title": "ES ZH",
                            "tier": "lite",
                            "commercialUse": True,
                            "routes": ["es-zh"],
                            "components": {
                                "asr": {
                                    "provider": "faster-whisper",
                                    "repoId": "fake/asr",
                                    "revision": "asr-revision",
                                },
                                "translation": {
                                    "provider": "marian-cascade-ct2",
                                    "stages": [
                                        {
                                            "provider": "marian-ct2",
                                            "repoId": "fake/es-en",
                                            "revision": "stage-one",
                                            "sourceLanguage": "es",
                                            "targetLanguage": "en",
                                        },
                                        {
                                            "provider": "marian-ct2",
                                            "repoId": "fake/en-zh",
                                            "revision": "stage-two",
                                            "sourceLanguage": "en",
                                            "targetLanguage": "zh",
                                        },
                                    ],
                                },
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return ModelCatalog(root / "models", catalog_file)

    def test_generic_cascade_downloader_supports_spanish_to_chinese(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            catalog = self._catalog(root)
            installer = FakeInstaller()
            calls = []

            def snapshot_download(*, repo_id, revision, local_dir, allow_patterns=None):
                calls.append((repo_id, revision, Path(local_dir).name))
                target = Path(local_dir)
                target.mkdir(parents=True, exist_ok=True)
                if repo_id == "fake/asr":
                    (target / "model.bin").write_bytes(b"asr")
                    return str(target)
                (target / "model.bin").write_bytes(b"mt")
                (target / "config.json").write_text("{}", encoding="utf-8")
                (target / "source.spm").write_bytes(b"src")
                (target / "target.spm").write_bytes(b"dst")
                return str(target)

            fake_hub = types.SimpleNamespace(snapshot_download=snapshot_download)
            with patch.dict(sys.modules, {"huggingface_hub": fake_hub}):
                pack = _download_lite_cascade_pack(
                    installer,
                    catalog,
                    "lite-es-zh",
                )

            self.assertEqual(pack.id, "lite-es-zh")
            self.assertEqual(
                [item[:2] for item in calls],
                [
                    ("fake/asr", "asr-revision"),
                    ("fake/es-en", "stage-one"),
                    ("fake/en-zh", "stage-two"),
                ],
            )
            self.assertTrue((pack.path / "components" / "translation" / "stage-1" / "model.bin").is_file())
            self.assertTrue((pack.path / "components" / "translation" / "stage-2" / "model.bin").is_file())
            metadata = json.loads((pack.path / "pack.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["id"], "lite-es-zh")
            self.assertEqual(installer.verify_calls[-1], ("lite-es-zh", "1.0.0"))


if __name__ == "__main__":
    unittest.main()
