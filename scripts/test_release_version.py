#!/usr/bin/env python3
"""Bloquea releases con metadatos de versión divergentes."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "1.0.5"
FAILURES: list[str] = []


def check(label: str, actual: str | None) -> None:
    if actual != EXPECTED:
        FAILURES.append(f"{label}: esperado {EXPECTED}, encontrado {actual!r}")


check("VERSION", (ROOT / "VERSION").read_text(encoding="utf-8").strip())
check("package.json", json.loads((ROOT / "package.json").read_text(encoding="utf-8")).get("version"))
check(
    "apps/desktop/package.json",
    json.loads((ROOT / "apps/desktop/package.json").read_text(encoding="utf-8")).get("version"),
)
check(
    "tauri.conf.json",
    json.loads((ROOT / "apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8")).get("version"),
)

extension = json.loads((ROOT / "apps/extension/manifest.json").read_text(encoding="utf-8"))
check("extension manifest version", extension.get("version"))
check("extension manifest version_name", extension.get("version_name"))

cargo = (ROOT / "Cargo.toml").read_text(encoding="utf-8")
workspace_package = re.search(
    r"(?ms)^\[workspace\.package\]\s*(.*?)(?=^\[|\Z)", cargo
)
if not workspace_package:
    FAILURES.append("Cargo.toml: falta [workspace.package]")
else:
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', workspace_package.group(1))
    check("Cargo.toml workspace.package", match.group(1) if match else None)

server = (ROOT / "services/ai/mily_ai/server.py").read_text(encoding="utf-8")
for marker in (
    '"version": "1.0.5"',
    'event("engine.ready", version="1.0.5", protocolVersion=1)',
):
    if marker not in server:
        FAILURES.append(f"Motor Python: falta {marker}")

frontend_api = (ROOT / "apps/desktop/src/lib/api.ts").read_text(encoding="utf-8")
for marker in (
    "version: '1.0.5-web-preview'",
    "activeModelPack: 'realtime-m2m100'",
):
    if marker not in frontend_api:
        FAILURES.append(f"Frontend API: falta {marker}")

ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
if "MilyVoiceTraductor-Full-1.0.5-Windows-x64-${{ github.sha }}" not in ci:
    FAILURES.append("CI: el artefacto Windows no está versionado como 1.0.5")

publish = (ROOT / ".github/workflows/publish-rc.yml").read_text(encoding="utf-8")
required_publish_markers = (
    "ARTIFACT_NAME: MilyVoiceTraductor-Full-1.0.5-Windows-x64-${{ github.event.workflow_run.head_sha }}",
    "RELEASE_TAG: v1.0.5",
    "RELEASE_TITLE: MilyVoiceTraductor 1.0.5",
    "release/MilyVoiceTraductor_1.0.5_x64-setup.exe",
)
for marker in required_publish_markers:
    if marker not in publish:
        FAILURES.append(f"Publish workflow: falta {marker}")

readme = (ROOT / "README.md").read_text(encoding="utf-8")
for marker in (
    "releases/download/v1.0.5/MilyVoiceTraductor_1.0.5_x64-setup.exe",
    "releases/tag/v1.0.5",
    "Release actual: 1.0.5",
):
    if marker not in readme:
        FAILURES.append(f"README: falta {marker}")

site = (ROOT / "apps/site/index.html").read_text(encoding="utf-8")
for marker in (
    "releases/download/v1.0.5/MilyVoiceTraductor_1.0.5_x64-setup.exe",
    "MilyVoiceTraductor 1.0.5",
    "1.0.5 · Runtime privado",
):
    if marker not in site:
        FAILURES.append(f"Sitio: falta {marker}")

if FAILURES:
    print("RELEASE VERSION CHECK FAILED")
    for failure in FAILURES:
        print(" -", failure)
    raise SystemExit(1)

print("RELEASE VERSION CHECK OK: 1.0.5")
