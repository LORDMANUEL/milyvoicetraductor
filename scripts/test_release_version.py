#!/usr/bin/env python3
"""Bloquea releases con metadatos de versión divergentes."""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "2.0.1"
FAILURES: list[str] = []


def check(label: str, actual: str | None) -> None:
    if actual != EXPECTED:
        FAILURES.append(f"{label}: esperado {EXPECTED}, encontrado {actual!r}")


check("VERSION", (ROOT / "VERSION").read_text(encoding="utf-8").strip())
check("package.json", json.loads((ROOT / "package.json").read_text(encoding="utf-8")).get("version"))
check("apps/desktop/package.json", json.loads((ROOT / "apps/desktop/package.json").read_text(encoding="utf-8")).get("version"))
check("tauri.conf.json", json.loads((ROOT / "apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8")).get("version"))
ai_project = tomllib.loads((ROOT / "services/ai/pyproject.toml").read_text(encoding="utf-8"))
check("services/ai/pyproject.toml", ai_project.get("project", {}).get("version"))
ai_init = (ROOT / "services/ai/mily_ai/__init__.py").read_text(encoding="utf-8")
internal_match = re.search(r'(?m)^__version__\s*=\s*"([^"]+)"', ai_init)
check("mily_ai.__version__", internal_match.group(1) if internal_match else None)
extension = json.loads((ROOT / "apps/extension/manifest.json").read_text(encoding="utf-8"))
check("extension manifest version", extension.get("version"))
check("extension manifest version_name", extension.get("version_name"))
cargo = (ROOT / "Cargo.toml").read_text(encoding="utf-8")
workspace_package = re.search(r"(?ms)^\[workspace\.package\]\s*(.*?)(?=^\[|\Z)", cargo)
if not workspace_package:
    FAILURES.append("Cargo.toml: falta [workspace.package]")
else:
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', workspace_package.group(1))
    check("Cargo.toml workspace.package", match.group(1) if match else None)
server = (ROOT / "services/ai/mily_ai/server.py").read_text(encoding="utf-8")
for marker in ('"version": "2.0.1"', 'event("engine.ready", version="2.0.1", protocolVersion=1)'):
    if marker not in server:
        FAILURES.append(f"Motor Python: falta {marker}")
frontend_api = (ROOT / "apps/desktop/src/lib/api.ts").read_text(encoding="utf-8")
for marker in ("version: '2.0.1-web-preview'", "activeModelPack: 'lite-en-es'"):
    if marker not in frontend_api:
        FAILURES.append(f"Frontend API: falta {marker}")
ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
for marker in (
    "MilyVoiceTraductor-Full-2.0.1-Windows-x64-${{ github.sha }}",
    "MilyVoiceTraductor-2.0.1-TargetMachineSimulation.json",
    "MilyVoiceTraductor-2.0.1-MoonshineLiteBench.json",
    "MilyVoiceTraductor-2.0.1-WhisperTinyLiteBench.json",
    "MilyVoiceTraductor-2.0.1-SherpaLiteBench.json",
):
    if marker not in ci:
        FAILURES.append(f"CI: falta {marker}")
if "MilyVoiceTraductor-2.0.1-MegaBench.json" in ci:
    FAILURES.append("CI: MegaBench Quality antiguo no debe ser gate del perfil 2 GiB")
publish = (ROOT / ".github/workflows/publish-rc.yml").read_text(encoding="utf-8")
required_publish_markers = (
    "ARTIFACT_NAME: MilyVoiceTraductor-Full-2.0.1-Windows-x64-${{ github.event.workflow_run.head_sha }}",
    "RELEASE_TAG: v2.0.1",
    "RELEASE_TITLE: MilyVoiceTraductor 2.0.1",
    "release/MilyVoiceTraductor_2.0.1_x64-setup.exe",
    "release/MilyVoiceTraductor-2.0.1-TargetMachineSimulation.json",
    "release/MilyVoiceTraductor-2.0.1-MoonshineLiteBench.json",
    "release/MilyVoiceTraductor-2.0.1-WhisperTinyLiteBench.json",
    "release/MilyVoiceTraductor-2.0.1-SherpaLiteBench.json",
)
for marker in required_publish_markers:
    if marker not in publish:
        FAILURES.append(f"Publish workflow: falta {marker}")
if "release/MilyVoiceTraductor-2.0.1-MegaBench.json" in publish:
    FAILURES.append("Publish workflow: MegaBench Quality antiguo no debe publicarse como gate Lite")
readme = (ROOT / "README.md").read_text(encoding="utf-8")
for marker in ("MilyVoiceTraductor 2.0.1", "2.0.1"):
    if marker not in readme:
        FAILURES.append(f"README: falta {marker}")
site = (ROOT / "apps/site/index.html").read_text(encoding="utf-8")
for marker in ("MilyVoiceTraductor 2.0.1", "Runtime privado"):
    if marker not in site:
        FAILURES.append(f"Sitio: falta {marker}")
# Los releases históricos se permiten dentro del archivo de versiones de Pages.
# Solo se bloquea copy que presente una candidata antigua como release actual.
for stale in ("2.0 RC", "Candidata actual"):
    if stale in site:
        FAILURES.append(f"Sitio: referencia obsoleta prohibida: {stale}")
if FAILURES:
    print("RELEASE VERSION CHECK FAILED")
    for failure in FAILURES:
        print(" -", failure)
    raise SystemExit(1)
print("RELEASE VERSION CHECK OK: 2.0.1")
