#!/usr/bin/env python3
"""Bloquea releases cuando la versión pública o su procedencia divergen."""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = "2.1.1"
RUST_MODULE_VERSION = "2.1.0"
FAILURES: list[str] = []


def check(label: str, actual: str | None, expected: str = EXPECTED) -> None:
    if actual != expected:
        FAILURES.append(f"{label}: esperado {expected}, encontrado {actual!r}")


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

# Los crates son módulos versionables de forma independiente. Un patch de producto
# no debe reescribir Cargo.lock si la API/artefactos Rust no cambiaron de versión.
cargo = (ROOT / "Cargo.toml").read_text(encoding="utf-8")
workspace_package = re.search(r"(?ms)^\[workspace\.package\]\s*(.*?)(?=^\[|\Z)", cargo)
if not workspace_package:
    FAILURES.append("Cargo.toml: falta [workspace.package]")
else:
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', workspace_package.group(1))
    check("Cargo.toml workspace.package (módulo interno)", match.group(1) if match else None, RUST_MODULE_VERSION)

frontend_api = (ROOT / "apps/desktop/src/lib/api.ts").read_text(encoding="utf-8")
for marker in ("version: '2.1.1-web-preview'", "activeModelPack: 'lite-en-es'"):
    if marker not in frontend_api:
        FAILURES.append(f"Frontend API: falta {marker}")

commands = (ROOT / "apps/desktop/src-tauri/src/commands/mod.rs").read_text(encoding="utf-8")
if "app.package_info().version.to_string()" not in commands:
    FAILURES.append("Desktop: get_app_status no usa la versión pública de Tauri")
if 'version: env!("CARGO_PKG_VERSION").to_string()' in commands:
    FAILURES.append("Desktop: la versión pública no puede depender de la semver interna del crate")

tier1_server = (ROOT / "services/ai/mily_ai/tier1_server.py").read_text(encoding="utf-8")
for marker in (
    "from . import __version__",
    'fields["version"] = __version__',
    'payload["version"] = __version__',
):
    if marker not in tier1_server:
        FAILURES.append(f"Tier1 server: falta versión pública dinámica: {marker}")

ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
for marker in (
    "MilyVoiceTraductor-2.1.0-TargetMachineSimulation.json",
    "MilyVoiceTraductor-2.1.0-MoonshineLiteBench.json",
    "MilyVoiceTraductor-2.1.0-WhisperTinyLiteBench.json",
    "MilyVoiceTraductor-2.1.0-SherpaLiteBench.json",
    "MilyVoiceTraductor-2.1.0-EsEnLiteBench.json",
    "MilyVoiceTraductor-2.1.0-EsZhLiteBench.json",
):
    if marker not in ci:
        FAILURES.append(f"CI: falta evidencia interna: {marker}")
if "MilyVoiceTraductor-2.1.0-MegaBench.json" in ci:
    FAILURES.append("CI: MegaBench Quality antiguo no debe ser gate del perfil 2 GiB")

certify = (ROOT / ".github/workflows/certify-pruebas.yml").read_text(encoding="utf-8")
for marker in (
    "MilyVoiceTraductor-Certified-2.1.1-Windows-x64-${{ env.CERTIFIED_SHA }}",
    "Assert exact certified checkout",
    "Spanish Lite real ES to EN benchmark",
    "Spanish Lite real ES to ZH benchmark",
    "Mandarin Lite experimental ZH to ES benchmark",
    "MilyVoiceTraductor-2.1.1-TargetMachineSimulation.json",
    "MilyVoiceTraductor-2.1.1-MoonshineLiteBench.json",
    "MilyVoiceTraductor-2.1.1-WhisperTinyLiteBench.json",
    "MilyVoiceTraductor-2.1.1-SherpaLiteBench.json",
    "MilyVoiceTraductor-2.1.1-EsEnLiteBench.json",
    "MilyVoiceTraductor-2.1.1-EsZhLiteBench.json",
):
    if marker not in certify:
        FAILURES.append(f"Exact-SHA certification: falta {marker}")
mandarin = certify.find("Mandarin Lite experimental ZH to ES benchmark")
rust = certify.find("- name: Rust tests", mandarin)
if mandarin < 0 or rust < 0 or "continue-on-error: true" not in certify[mandarin:rust]:
    FAILURES.append("Exact-SHA certification: ZH→ES experimental debe ser no bloqueante")
release_bundle = certify[certify.find("Prepare release bundle and SHA-256 checksums"):certify.find("Collect sanitized diagnostics")]
if "ZhEsLiteBench" in release_bundle:
    FAILURES.append("Exact-SHA certification: ZH→ES experimental no debe entrar al bundle público")

publish = (ROOT / ".github/workflows/publish-rc.yml").read_text(encoding="utf-8")
required_publish_markers = (
    "ARTIFACT_NAME: MilyVoiceTraductor-Certified-2.1.1-Windows-x64-${{ github.event.workflow_run.head_sha }}",
    "RELEASE_TAG: v2.1.1",
    "RELEASE_TITLE: MilyVoiceTraductor 2.1.1 Beta",
    "release/MilyVoiceTraductor_2.1.1_x64-setup.exe",
    "release/MilyVoiceTraductor-2.1.1-TargetMachineSimulation.json",
    "release/MilyVoiceTraductor-2.1.1-MoonshineLiteBench.json",
    "release/MilyVoiceTraductor-2.1.1-WhisperTinyLiteBench.json",
    "release/MilyVoiceTraductor-2.1.1-SherpaLiteBench.json",
    "release/MilyVoiceTraductor-2.1.1-EsEnLiteBench.json",
    "release/MilyVoiceTraductor-2.1.1-EsZhLiteBench.json",
    "docs/release/RELEASE_NOTES_2.1.1.md",
    "sha256sum -c SHA256SUMS.txt",
    "cmp release/SHA256SUMS.txt existing-release/SHA256SUMS.txt",
    "! grep -Fq 'ZhEsLiteBench' <<<\"$assets\"",
)
for marker in required_publish_markers:
    if marker not in publish:
        FAILURES.append(f"Publish workflow: falta {marker}")
for forbidden in (
    "RELEASE_TAG: v2.1.0",
    "git tag -f",
    "git push origin \"refs/tags/$RELEASE_TAG\" --force",
    "gh release edit",
    "--clobber",
    "test -f release/MilyVoiceTraductor-2.1.1-ZhEsLiteBench.json",
    "grep -Fxq 'MilyVoiceTraductor-2.1.1-ZhEsLiteBench.json'",
):
    if forbidden in publish:
        FAILURES.append(f"Publish workflow: operación mutable/prohibida: {forbidden}")

site = (ROOT / "apps/site/index.html").read_text(encoding="utf-8")
for stale in ("2.0 RC", "Candidata actual"):
    if stale in site:
        FAILURES.append(f"Sitio: referencia obsoleta prohibida: {stale}")

if FAILURES:
    print("RELEASE VERSION CHECK FAILED")
    for failure in FAILURES:
        print(" -", failure)
    raise SystemExit(1)
print("RELEASE VERSION CHECK OK: 2.1.1 product + modular Rust + immutable beta publisher")
