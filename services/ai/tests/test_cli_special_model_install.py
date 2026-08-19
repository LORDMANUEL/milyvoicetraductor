import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mily_ai import cli
from mily_ai.models import InstalledPack


class FakeCatalog:
    def __init__(self, models_dir):
        self.models_dir = Path(models_dir)

    def definition(self, pack_id):
        return {
            "id": pack_id,
            "version": "1.0.0",
            "tier": "lite",
            "routes": ["en-es"],
            "ramMb": 780,
            "vramMb": 0,
            "sharedGpuMb": 0,
            "engine": "moonshine-local",
            "supportedBackends": ["cpu"],
        }


class FakeInstaller:
    def __init__(self, catalog):
        self.catalog = catalog
        self.activated = None

    def activate(self, pack_id, version):
        self.activated = (pack_id, version)


class CliSpecialModelInstallTests(unittest.TestCase):
    def test_normal_install_uses_special_download_then_activates(self):
        with tempfile.TemporaryDirectory() as tmp:
            models_dir = Path(tmp) / "models"
            models_dir.mkdir()
            paths = SimpleNamespace(models_dir=models_dir)
            pack_path = models_dir / "packs" / "fast-moonshine-en-es" / "1.0.0"
            pack_path.mkdir(parents=True)
            pack = InstalledPack(
                "fast-moonshine-en-es",
                "1.0.0",
                pack_path,
                False,
                "Moonshine",
                True,
            )
            calls = []
            installer_holder = {}

            def installer_factory(catalog):
                value = FakeInstaller(catalog)
                installer_holder["value"] = value
                return value

            def download(installer, catalog, pack_id):
                calls.append((installer, catalog, pack_id))
                return pack

            args = SimpleNamespace(
                model_action="install",
                pack_id="fast-moonshine-en-es",
                download_only=False,
            )
            output = io.StringIO()
            with patch("mily_ai.cli._paths", return_value=paths), patch(
                "mily_ai.cli.ModelCatalog", FakeCatalog
            ), patch(
                "mily_ai.cli.HuggingFacePackInstaller", side_effect=installer_factory
            ), patch(
                "mily_ai.cli.download_pack", side_effect=download
            ), redirect_stdout(output):
                code = cli.cmd_models(args)

            self.assertEqual(code, 0)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][2], "fast-moonshine-en-es")
            self.assertEqual(
                installer_holder["value"].activated,
                ("fast-moonshine-en-es", "1.0.0"),
            )
            self.assertIn('"id": "fast-moonshine-en-es"', output.getvalue())

    def test_download_only_never_activates(self):
        with tempfile.TemporaryDirectory() as tmp:
            models_dir = Path(tmp) / "models"
            models_dir.mkdir()
            paths = SimpleNamespace(models_dir=models_dir)
            pack_path = models_dir / "packs" / "fast-moonshine-en-es" / "1.0.0"
            pack_path.mkdir(parents=True)
            pack = InstalledPack(
                "fast-moonshine-en-es",
                "1.0.0",
                pack_path,
                False,
                "Moonshine",
                True,
            )
            installer_holder = {}

            def installer_factory(catalog):
                value = FakeInstaller(catalog)
                installer_holder["value"] = value
                return value

            args = SimpleNamespace(
                model_action="install",
                pack_id="fast-moonshine-en-es",
                download_only=True,
            )
            with patch("mily_ai.cli._paths", return_value=paths), patch(
                "mily_ai.cli.ModelCatalog", FakeCatalog
            ), patch(
                "mily_ai.cli.HuggingFacePackInstaller", side_effect=installer_factory
            ), patch("mily_ai.cli.download_pack", return_value=pack), redirect_stdout(
                io.StringIO()
            ):
                code = cli.cmd_models(args)

            self.assertEqual(code, 0)
            self.assertIsNone(installer_holder["value"].activated)


if __name__ == "__main__":
    unittest.main()
