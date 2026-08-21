#!/usr/bin/env python3
"""Bloquea releases estables 2.0.2 con metadatos o artefactos divergentes."""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "2.0.2"
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

ai_project = tomllib.loads((ROOT / "services/ai/pyproject.toml").read_text(encoding="utf-8"))
check("services/ai/pyproject.toml", ai_project.get("project", {}).get("version"))
ai_init = (ROOT / "services/ai/mily_ai/__init__.py").read_text(encoding="utf-8")
internal_match = re.search(r'(?m)^__version__\s*=\s*"([^"]+)"', ai_init)
check("mily_ai.__version__", internal_match.group(1) if internal_match else None)

extension = json.loads((ROOT / "apps/extension/manifest.json").read_text(encoding="utf-8"))
check("extension manifest version", extension.get("version"))
check("extension manifest version_name", extension.get("version_name"))
if EXPECTED not in str(extension.get("description", "")):
    FAILURES.append("Extension manifest: la descripción no identifica 2.0.2")

cargo = (ROOT / "Cargo.toml").read_text(encoding="utf-8")
workspace_package = re.search(r"(?ms)^\[workspace\.package\]\s*(.*?)(?=^\[|\Z)", cargo)
if not workspace_package:
    FAILURES.append("Cargo.toml: falta [workspace.package]")
else:
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', workspace_package.group(1))
    check("Cargo.toml workspace.package", match.group(1) if match else None)

server = (ROOT / "services/ai/mily_ai/server.py").read_text(encoding="utf-8")
for marker in (
    '"version": "2.0.2"',
    'event("engine.ready", version="2.0.2", protocolVersion=1)',
):
    if marker not in server:
        FAILURES.append(f"Motor Python: falta {marker}")

frontend_api = (ROOT / "apps/desktop/src/lib/api.ts").read_text(encoding="utf-8")
if "version: '2.0.2-web-preview'" not in frontend_api:
    FAILURES.append("Frontend API: falta versión web-preview 2.0.2")
app = (ROOT / "apps/desktop/src/App.svelte").read_text(encoding="utf-8")
if "version: '2.0.2'" not in app or "version: '1.0.0-rc.1'" in app:
    FAILURES.append("App.svelte: estado inicial de versión no está en 2.0.2")

ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
for marker in (
    "MilyVoiceTraductor-Full-2.0.2-Windows-x64-${{ github.sha }}",
    "MilyVoiceTraductor-2.0.2-MegaBench.json",
    "Verify failed bootstrap makes NSIS fail",
    "test-nsis-bootstrap-failure.ps1",
    "Verify clean first run does not download models",
):
    if marker not in ci:
        FAILURES.append(f"CI: falta {marker}")

publish = (ROOT / ".github/workflows/publish-rc.yml").read_text(encoding="utf-8")
for marker in (
    "ARTIFACT_NAME: MilyVoiceTraductor-Full-2.0.2-Windows-x64-${{ github.event.workflow_run.head_sha }}",
    "RELEASE_TAG: v2.0.2",
    "RELEASE_TITLE: MilyVoiceTraductor 2.0.2",
    "MilyVoiceTraductor_2.0.2_x64-setup.exe",
    "MilyVoiceTraductor-2.0.2-MegaBench.json",
    "RELEASE_NOTES_2.0.2.md",
    "head_branch == 'stable/2.0.x'",
):
    if marker not in publish:
        FAILURES.append(f"Publish workflow: falta {marker}")

readme = (ROOT / "README.md").read_text(encoding="utf-8")
for marker in (
    "MilyVoiceTraductor 2.0.2",
    "v2.0.2/MilyVoiceTraductor_2.0.2_x64-setup.exe",
    "no descarga modelos",
):
    if marker not in readme:
        FAILURES.append(f"README: falta {marker}")

site = (ROOT / "apps/site/index.html").read_text(encoding="utf-8")
for marker in (
    "MilyVoiceTraductor 2.0.2",
    "2.0.2 · Runtime privado",
    "v2.0.2/MilyVoiceTraductor_2.0.2_x64-setup.exe",
    "Gestor de modelos",
):
    if marker not in site:
        FAILURES.append(f"Sitio: falta {marker}")

for required in (
    ROOT / "docs/release/RELEASE_NOTES_2.0.2.md",
    ROOT / "installer/windows/test-nsis-bootstrap-failure.ps1",
    ROOT / "installer/windows/test-runtime-import-diagnostics.ps1",
    ROOT / "installer/windows/test-first-run-no-model-download.ps1",
):
    if not required.is_file():
        FAILURES.append(f"Falta archivo de release/gate: {required.relative_to(ROOT)}")

if FAILURES:
    print("RELEASE VERSION CHECK FAILED")
    for failure in FAILURES:
        print(" -", failure)
    raise SystemExit(1)

print("RELEASE VERSION CHECK OK: 2.0.2")
