from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REQUIREMENTS = ROOT / "services/ai/requirements.runtime.txt"
BUILDER = ROOT / "installer/windows/build-python-runtime.ps1"
CI = ROOT / ".github/workflows/ci.yml"
FRONTEND_LOCK = ROOT / "apps/desktop/package-lock.json"


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

    def test_frontend_dependency_graph_is_committed_and_ci_uses_npm_ci(self) -> None:
        self.assertTrue(FRONTEND_LOCK.is_file(), "apps/desktop/package-lock.json debe versionarse.")
        ci = CI.read_text(encoding="utf-8")
        self.assertIn(
            "npm ci --prefix apps/desktop --workspaces=false --legacy-peer-deps --no-audit --no-fund",
            ci,
        )
        self.assertNotIn(
            "npm install --prefix apps/desktop --workspaces=false --legacy-peer-deps --no-audit --no-fund",
            ci,
        )

    def test_ci_never_updates_the_committed_cargo_lockfile(self) -> None:
        ci = CI.read_text(encoding="utf-8")
        required = (
            "cargo test --locked --workspace --exclude milyvoicetraductor-desktop",
            "cargo clippy --locked --workspace --all-targets --exclude milyvoicetraductor-desktop -- -D warnings",
            "cargo build --locked -p mily-bridge --release",
            "cargo test --locked --workspace",
            "cargo clippy --locked --workspace --all-targets -- -D warnings",
            "cargo build --locked -p milyvoicetraductor-desktop --release",
        )
        for command in required:
            self.assertIn(command, ci)


if __name__ == "__main__":
    unittest.main()
