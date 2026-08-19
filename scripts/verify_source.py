#!/usr/bin/env python3
"""Verificación offline de integridad para el paquete fuente."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILURES: list[str] = []


def fail(message: str) -> None:
    FAILURES.append(message)


def run(label: str, command: list[str], cwd: Path = ROOT) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        fail(f"{label}: {result.stdout[-1200:]} {result.stderr[-1200:]}")


for path in ROOT.rglob("*.json"):
    if any(part in {"node_modules", "target", "models", "cache"} for part in path.parts):
        continue
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"JSON inválido {path.relative_to(ROOT)}: {exc}")

catalog_a = json.loads((ROOT / "resources/model-packs.json").read_text(encoding="utf-8"))
catalog_b = json.loads((ROOT / "services/ai/mily_ai/model-packs.json").read_text(encoding="utf-8"))
if catalog_a != catalog_b:
    fail("Los dos catálogos de modelos no coinciden.")

commit_sha = re.compile(r"^[0-9a-f]{40}$")
for pack in catalog_a.get("packs", []):
    for component_name, component in pack.get("components", {}).items():
        repo_id = str(component.get("repoId", "")).strip()
        provider = str(component.get("provider", "")).strip()
        if repo_id:
            if not commit_sha.fullmatch(str(component.get("revision", ""))):
                fail(f"Modelo sin revisión SHA fijada: {pack.get('id')}/{component_name}")
            continue
        if provider == "moonshine":
            if component.get("runtimeVersion") != "0.1.0":
                fail(f"Moonshine sin runtime fijado: {pack.get('id')}/{component_name}")
            if component.get("language") != "en" or component.get("modelArch") != 2:
                fail(f"Moonshine sin arquitectura/lenguaje fijados: {pack.get('id')}/{component_name}")
            continue
        if provider == "marian-cascade-ct2":
            stages = component.get("stages")
            if not isinstance(stages, list) or len(stages) != 2:
                fail(f"Cascada Marian inválida: {pack.get('id')}/{component_name}")
                continue
            previous_target = None
            for index, stage in enumerate(stages, start=1):
                label = f"{pack.get('id')}/{component_name}/stage-{index}"
                if not isinstance(stage, dict):
                    fail(f"Etapa Marian inválida: {label}")
                    continue
                if str(stage.get("provider", "")).strip() != "marian-ct2":
                    fail(f"Proveedor de etapa Marian inválido: {label}")
                stage_repo = str(stage.get("repoId", "")).strip()
                if not stage_repo:
                    fail(f"Etapa Marian sin repoId: {label}")
                if not commit_sha.fullmatch(str(stage.get("revision", ""))):
                    fail(f"Etapa Marian sin revisión SHA fijada: {label}")
                source = str(stage.get("sourceLanguage", "")).strip().lower()
                target = str(stage.get("targetLanguage", "")).strip().lower()
                if not source or not target:
                    fail(f"Etapa Marian sin dirección explícita: {label}")
                if previous_target is not None and source != previous_target:
                    fail(f"Cascada Marian discontinua: {label}")
                previous_target = target
            continue
        fail(f"Componente sin procedencia reproducible: {pack.get('id')}/{component_name}")

version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
package_version = json.loads((ROOT / "package.json").read_text(encoding="utf-8")).get("version")
tauri_config = json.loads((ROOT / "apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
windows_config = json.loads((ROOT / "apps/desktop/src-tauri/tauri.windows.conf.json").read_text(encoding="utf-8"))
tauri_version = tauri_config.get("version")
if package_version != version or tauri_version != version:
    fail(f"Versiones divergentes: VERSION={version}, package={package_version}, tauri={tauri_version}")

resources = windows_config.get("bundle", {}).get("resources", {})
expected_resources = {
    "../../../services/ai/": "bootstrap/ai/",
    "../../extension/": "bootstrap/extension/",
    "../../../dist/runtime/milyvoice-python-runtime.zip": "bootstrap/runtime/milyvoice-python-runtime.zip",
    "../../../dist/runtime/milyvoice-python-runtime.zip.sha256": "bootstrap/runtime/milyvoice-python-runtime.zip.sha256",
    "../../../target/release/milyvoice-bridge.exe": "bootstrap/bridge/milyvoice-bridge.exe",
    "../../../installer/windows/setup-installed.ps1": "bootstrap/setup-installed.ps1",
    "../../../installer/windows/register-native-host.ps1": "bootstrap/register-native-host.ps1",
    "../../../installer/windows/native-host-template.json": "bootstrap/native-host-template.json",
}
if resources != expected_resources:
    fail("El bundle Windows no contiene exactamente runtime, motor, extensión y bridge requeridos.")

nsis = tauri_config.get("bundle", {}).get("windows", {}).get("nsis", {})
if nsis.get("installerHooks") != "./windows/hooks.nsh":
    fail("El instalador NSIS no referencia windows/hooks.nsh.")

hooks_path = ROOT / "apps/desktop/src-tauri/windows/hooks.nsh"
bootstrap_path = ROOT / "installer/windows/setup-installed.ps1"
register_path = ROOT / "installer/windows/register-native-host.ps1"
runtime_builder = ROOT / "installer/windows/build-python-runtime.ps1"
native_template = ROOT / "installer/windows/native-host-template.json"
model_service_path = ROOT / "crates/mily-models/src/lib.rs"
desktop_main_path = ROOT / "apps/desktop/src-tauri/src/main.rs"

for required in (
    hooks_path,
    bootstrap_path,
    register_path,
    runtime_builder,
    native_template,
    model_service_path,
    desktop_main_path,
):
    if not required.is_file():
        fail(f"Falta componente Windows: {required.relative_to(ROOT)}")

if hooks_path.is_file():
    hooks_text = hooks_path.read_text(encoding="utf-8")
    for marker in ("NSIS_HOOK_POSTINSTALL", "NSIS_HOOK_PREUNINSTALL", "setup-installed.ps1", "register-native-host.ps1"):
        if marker not in hooks_text:
            fail(f"Hook NSIS incompleto: falta {marker}.")

if bootstrap_path.is_file():
    bootstrap_text = bootstrap_path.read_text(encoding="utf-8")
    for marker in ("milyvoice-python-runtime.zip", "register-native-host.ps1", "milyvoice-bridge.exe", "diagnose", "HF_HUB_DISABLE_TELEMETRY"):
        if marker not in bootstrap_text:
            fail(f"Bootstrap Windows incompleto: falta {marker}.")
    for prohibited in ("winget install", "-m venv", "-m pip install", "models `"):
        if prohibited in bootstrap_text:
            fail(f"Bootstrap normal todavía depende de instalación online: {prohibited}")

if model_service_path.is_file():
    model_service = model_service_path.read_text(encoding="utf-8")
    for marker in ("CREATE_NO_WINDOW", "command.creation_flags(CREATE_NO_WINDOW)"):
        if marker not in model_service:
            fail(f"El instalador/optimizador de modelos puede abrir una consola visible en Windows: falta {marker}")

if desktop_main_path.is_file():
    desktop_main = desktop_main_path.read_text(encoding="utf-8")
    marker = '#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]'
    if marker not in desktop_main:
        fail("El Desktop Release puede abrir una consola visible en Windows: falta windows_subsystem=windows.")

if runtime_builder.is_file():
    builder_text = runtime_builder.read_text(encoding="utf-8")
    for marker in ("3.13.13", "142666a4a9079507815d395b9bfb73546ec391003d385beb559a9d68fb240062", "milyvoice-python-runtime.zip"):
        if marker not in builder_text:
            fail(f"Builder de runtime no está fijado/reproducible: falta {marker}")

if native_template.is_file():
    native = json.loads(native_template.read_text(encoding="utf-8"))
    origins = native.get("allowed_origins", [])
    expected_origin = "chrome-extension://edcpjonegaempcifgodcmgejbcpdpddm/"
    if origins != [expected_origin] or "*" in origins:
        fail("Native Messaging allowed_origins debe contener únicamente la extensión fijada.")

manifest = json.loads((ROOT / "apps/extension/manifest.json").read_text(encoding="utf-8"))
if "nativeMessaging" not in manifest.get("permissions", []):
    fail("La extensión no declara nativeMessaging.")
if not manifest.get("key"):
    fail("La extensión no fija identidad mediante clave pública.")

for rust_path in ROOT.rglob("*.rs"):
    if any(part in {"target", "node_modules", "dist"} for part in rust_path.parts):
        continue
    rust_lines = rust_path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(rust_lines[:-1]):
        if line.rstrip().endswith(";") and rust_lines[index + 1].lstrip().startswith("."):
            fail(f"Cadena Rust cortada por ';': {rust_path.relative_to(ROOT)}:{index + 1}")

placeholder = re.compile(r"\b(TODO|TBD|FIXME|CHANGEME)\b")
secret = re.compile(r"(?i)(api[_-]?key|password|passwd|secret|token)\s*[:=]\s*[\"\'][A-Za-z0-9_\-/+=]{16,}[\"\']")
skip_parts = {".git", "node_modules", "target", "dist", "__pycache__", ".pytest_cache"}
for path in ROOT.rglob("*"):
    if not path.is_file() or any(part in skip_parts for part in path.parts):
        continue
    if path.suffix.lower() in {".png", ".ico", ".zip", ".exe", ".dll", ".db"}:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    is_plan_doc = path.relative_to(ROOT).as_posix().startswith("docs/superpowers/plans/")
    if placeholder.search(text) and "verify_source.py" not in path.name and not is_plan_doc:
        fail(f"Placeholder pendiente: {path.relative_to(ROOT)}")
    if secret.search(text) and path.name != ".env.example":
        fail(f"Posible secreto: {path.relative_to(ROOT)}")

for path in ROOT.rglob("*"):
    if path.is_file() and path.stat().st_size > 25 * 1024 * 1024:
        fail(f"Archivo >25MB no permitido en fuente: {path.relative_to(ROOT)}")

run("AI unit tests", [sys.executable, "scripts/run_ai_tests.py", "--timeout", "120"])
run("Extension guard", [sys.executable, "scripts/test_extension.py"])
run("Site smoke", [sys.executable, "scripts/test_site.py"])
run("Privacy scan", [sys.executable, "scripts/privacy_scan.py", "."])
for path in sorted((ROOT / "apps/extension").glob("*.js")):
    run(f"node --check {path.name}", ["node", "--check", str(path)])

if FAILURES:
    print("SOURCE VERIFICATION FAILED")
    for item in FAILURES:
        print(" -", item)
    raise SystemExit(1)
print("SOURCE VERIFICATION OK")
