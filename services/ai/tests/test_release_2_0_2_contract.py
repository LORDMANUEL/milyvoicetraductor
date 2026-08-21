from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXPECTED = "2.0.2"


class StableRelease202ContractTests(unittest.TestCase):
    def test_product_metadata_is_2_0_2_everywhere_user_visible(self) -> None:
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), EXPECTED)
        self.assertEqual(json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"], EXPECTED)
        self.assertEqual(json.loads((ROOT / "apps/desktop/package.json").read_text(encoding="utf-8"))["version"], EXPECTED)
        tauri = json.loads((ROOT / "apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
        self.assertEqual(tauri["version"], EXPECTED)
        self.assertIn(EXPECTED, tauri["bundle"]["longDescription"])

        cargo = (ROOT / "Cargo.toml").read_text(encoding="utf-8")
        workspace = re.search(r"(?ms)^\[workspace\.package\]\s*(.*?)(?=^\[|\Z)", cargo)
        self.assertIsNotNone(workspace)
        self.assertIn(f'version = "{EXPECTED}"', workspace.group(1) if workspace else "")

        ai = tomllib.loads((ROOT / "services/ai/pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(ai["project"]["version"], EXPECTED)
        ai_init = (ROOT / "services/ai/mily_ai/__init__.py").read_text(encoding="utf-8")
        self.assertIn(f'__version__ = "{EXPECTED}"', ai_init)
        server = (ROOT / "services/ai/mily_ai/server.py").read_text(encoding="utf-8")
        self.assertIn(f'"version": "{EXPECTED}"', server)
        self.assertIn(f'event("engine.ready", version="{EXPECTED}", protocolVersion=1)', server)

        extension = json.loads((ROOT / "apps/extension/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(extension["version"], EXPECTED)
        self.assertEqual(extension["version_name"], EXPECTED)
        self.assertIn(EXPECTED, extension["description"])

        api = (ROOT / "apps/desktop/src/lib/api.ts").read_text(encoding="utf-8")
        self.assertIn(f"version: '{EXPECTED}-web-preview'", api)
        app = (ROOT / "apps/desktop/src/App.svelte").read_text(encoding="utf-8")
        self.assertNotIn("version: '1.0.0-rc.1'", app)
        self.assertIn(f"version: '{EXPECTED}'", app)

    def test_release_artifacts_and_docs_are_2_0_2(self) -> None:
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("MilyVoiceTraductor-Full-2.0.2-Windows-x64-${{ github.sha }}", ci)
        self.assertIn("MilyVoiceTraductor-2.0.2-MegaBench.json", ci)
        self.assertIn("test-nsis-bootstrap-failure.ps1", ci)

        publisher = (ROOT / ".github/workflows/publish-rc.yml").read_text(encoding="utf-8")
        for marker in (
            "MilyVoiceTraductor-Full-2.0.2-Windows-x64-${{ github.event.workflow_run.head_sha }}",
            "RELEASE_TAG: v2.0.2",
            "RELEASE_TITLE: MilyVoiceTraductor 2.0.2",
            "MilyVoiceTraductor_2.0.2_x64-setup.exe",
            "MilyVoiceTraductor-2.0.2-MegaBench.json",
        ):
            self.assertIn(marker, publisher)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("MilyVoiceTraductor 2.0.2", readme)
        self.assertIn("v2.0.2/MilyVoiceTraductor_2.0.2_x64-setup.exe", readme)
        site = (ROOT / "apps/site/index.html").read_text(encoding="utf-8")
        self.assertIn("MilyVoiceTraductor 2.0.2", site)
        self.assertIn("v2.0.2/MilyVoiceTraductor_2.0.2_x64-setup.exe", site)
        self.assertTrue((ROOT / "docs/release/RELEASE_NOTES_2.0.2.md").is_file())


if __name__ == "__main__":
    unittest.main()
