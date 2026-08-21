from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REQUIREMENTS = ROOT / "services/ai/requirements.runtime.txt"
BUILDER = ROOT / "installer/windows/build-python-runtime.ps1"


class RuntimeReproducibilityContractTests(unittest.TestCase):
    def test_every_direct_runtime_dependency_is_exactly_pinned(self) -> None:
        lines = [
            line.strip()
            for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertGreater(len(lines), 10)
        for line in lines:
            self.assertRegex(
                line,
                r"^[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?==[^,;<>~=!\s]+$",
                f"Dependencia no fijada exactamente: {line}",
            )

    def test_runtime_manifest_records_exact_installed_package_inventory(self) -> None:
        source = BUILDER.read_text(encoding="utf-8")
        for marker in (
            "importlib.metadata",
            "installedPackages",
            "Name",
            "Version",
        ):
            self.assertIn(marker, source)

    def test_runtime_build_never_upgrades_dependencies_implicitly(self) -> None:
        source = BUILDER.read_text(encoding="utf-8")
        self.assertNotRegex(source, re.compile(r"pip install[^\n]*(?:--upgrade|-U)(?:\s|$)", re.IGNORECASE))


if __name__ == "__main__":
    unittest.main()
