#!/usr/bin/env python3
"""Finaliza metadatos activos de MilyVoiceTraductor 2.1.0 de forma reproducible."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = "2.0.1"
TARGET = "2.1.0"

ACTIVE_TEXT_FILES = (
    "VERSION",
    "package.json",
    "apps/desktop/package.json",
    "apps/desktop/src-tauri/tauri.conf.json",
    "apps/desktop/src/lib/api.ts",
    "apps/extension/manifest.json",
    "Cargo.toml",
    "services/ai/pyproject.toml",
    "services/ai/mily_ai/__init__.py",
    "services/ai/mily_ai/server.py",
    ".github/workflows/ci.yml",
    ".github/workflows/publish-rc.yml",
    "scripts/test_release_version.py",
    "services/ai/tests/test_engine_hub_ci_release_policy.py",
    "installer/windows/test-engine-hub-target-machine.ps1",
    "installer/windows/test-moonshine-lite.ps1",
    "installer/windows/test-whisper-tiny-lite.ps1",
    "installer/windows/test-sherpa-lite.ps1",
    "installer/windows/test-zh-es-lite.ps1",
    "installer/windows/test-nsis-installer.ps1",
    "README.md",
    "apps/site/index.html",
)


def replace_active_version(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"Falta archivo de versión activo: {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    if CURRENT not in text and TARGET not in text:
        raise SystemExit(
            f"{path.relative_to(ROOT)} no contiene ni {CURRENT} ni {TARGET}; revisión manual requerida"
        )
    path.write_text(text.replace(CURRENT, TARGET), encoding="utf-8")


def update_package_lock(path: Path) -> None:
    if not path.is_file():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("name") == "milyvoicetraductor":
        payload["version"] = TARGET
    packages = payload.get("packages")
    if isinstance(packages, dict):
        root = packages.get("")
        if isinstance(root, dict) and root.get("name") == "milyvoicetraductor":
            root["version"] = TARGET
        desktop = packages.get("apps/desktop")
        if isinstance(desktop, dict) and desktop.get("name") == "@milyvoice/desktop":
            desktop["version"] = TARGET
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_cargo_lock(path: Path) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    owned = {
        "mily-core",
        "mily-config",
        "mily-database",
        "mily-logging",
        "mily-cache",
        "mily-system",
        "mily-compute",
        "mily-engine",
        "mily-models",
        "mily-sessions",
        "mily-bridge",
        "milyvoicetraductor-desktop",
    }

    def rewrite(block_match: re.Match[str]) -> str:
        block = block_match.group(0)
        name_match = re.search(r'(?m)^name = "([^"]+)"$', block)
        if not name_match or name_match.group(1) not in owned:
            return block
        return re.sub(
            rf'(?m)^version = "{re.escape(CURRENT)}"$',
            f'version = "{TARGET}"',
            block,
        )

    updated = re.sub(r'(?ms)^\[\[package\]\]\n.*?(?=^\[\[package\]\]|\Z)', rewrite, text)
    path.write_text(updated, encoding="utf-8")


def assert_no_stale_active_version() -> None:
    stale: list[str] = []
    for relative in ACTIVE_TEXT_FILES:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        if CURRENT in text:
            stale.append(relative)
    if stale:
        raise SystemExit("Quedaron referencias activas 2.0.1: " + ", ".join(stale))


for relative in ACTIVE_TEXT_FILES:
    replace_active_version(ROOT / relative)

update_package_lock(ROOT / "package-lock.json")
update_package_lock(ROOT / "apps/desktop/package-lock.json")
update_cargo_lock(ROOT / "Cargo.lock")
assert_no_stale_active_version()

print(f"RELEASE_METADATA_FINALIZED {TARGET}")
