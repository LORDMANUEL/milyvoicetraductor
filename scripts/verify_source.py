#!/usr/bin/env python3
"""Verificación offline de integridad para el paquete fuente.

No sustituye cargo/npm CI, pero bloquea secretos, placeholders, JSON roto,
catálogos divergentes y artefactos que no deben publicarse.
"""
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


# JSON/Tauri/manifest/catalog integrity.
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

# Cada componente debe quedar fijado a un commit completo para reproducibilidad.
commit_sha = re.compile(r"^[0-9a-f]{40}$")
for pack in catalog_a.get("packs", []):
    for component_name, component in pack.get("components", {}).items():
        if not commit_sha.fullmatch(str(component.get("revision", ""))):
            fail(f"Modelo sin revisión SHA fijada: {pack.get('id')}/{component_name}")

# Las versiones públicas deben permanecer sincronizadas.
version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
package_version = json.loads((ROOT / "package.json").read_text(encoding="utf-8")).get("version")
tauri_version = json.loads((ROOT / "apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8")).get("version")
if package_version != version or tauri_version != version:
    fail(f"Versiones divergentes: VERSION={version}, package={package_version}, tauri={tauri_version}")

# Guardia sintáctica mínima de Rust útil cuando el host no trae cargo.
# Detecta una cadena de métodos cortada por ';' justo antes de otro `.metodo()`.
for rust_path in ROOT.rglob("*.rs"):
    if any(part in {"target", "node_modules", "dist"} for part in rust_path.parts):
        continue
    rust_lines = rust_path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(rust_lines[:-1]):
        if line.rstrip().endswith(";") and rust_lines[index + 1].lstrip().startswith("."):
            fail(f"Cadena Rust cortada por ';': {rust_path.relative_to(ROOT)}:{index + 1}")

# No placeholders/secretos en archivos de producto.
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

# Prohibir pesos o artefactos enormes en fuente.
for path in ROOT.rglob("*"):
    if path.is_file() and path.stat().st_size > 25 * 1024 * 1024:
        fail(f"Archivo >25MB no permitido en fuente: {path.relative_to(ROOT)}")

# Validaciones ejecutables que no requieren descargar dependencias.
run("AI unit tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"], ROOT / "services/ai")
run("Extension guard", [sys.executable, "scripts/test_extension.py"])
run("Site smoke", [sys.executable, "scripts/test_site.py"])
run("Privacy scan", [sys.executable, "scripts/privacy_scan.py", "."])

# Node puede validar sintaxis JS de la extensión sin npm install.
for path in sorted((ROOT / "apps/extension").glob("*.js")):
    run(f"node --check {path.name}", ["node", "--check", str(path)])

if FAILURES:
    print("SOURCE VERIFICATION FAILED")
    for item in FAILURES:
        print(" -", item)
    raise SystemExit(1)
print("SOURCE VERIFICATION OK")
