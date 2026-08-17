#!/usr/bin/env python3
"""Guardia conservadora contra secretos/datos personales accidentales.

No pretende reemplazar un scanner especializado. Busca patrones de alto riesgo
sin imprimir el valor encontrado, para evitar convertir CI en otra filtración.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SCAN_EXTENSIONS = {".rs", ".ts", ".svelte", ".js", ".json", ".toml", ".md", ".yml", ".yaml", ".html", ".css", ".py", ".env", ".example"}
SKIP_DIRS = {".git", "node_modules", "target", "dist", "models", "cache", "logs"}
PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "openai-key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "assigned-secret": re.compile(r"(?i)\b(?:password|passwd|api[_-]?key|secret|token)\s*[:=]\s*[\"'][A-Za-z0-9_./+=-]{16,}[\"']"),
    "windows-user-home": re.compile(r"(?i)[A-Z]:\\Users\\(?!<)[^\\\s]+\\"),
    "unix-user-home": re.compile(r"/(?:home|Users)/(?!<)[^/\s]+/"),
}

findings: list[tuple[str, str]] = []
for path in ROOT.rglob("*"):
    if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
        continue
    if path.suffix not in SCAN_EXTENSIONS and path.name not in {".env.example", "VERSION"}:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    # Tests/documentación contienen nombres de patrones deliberadamente; solo
    # se exceptúan ejemplos inequívocamente sintéticos dentro del scanner mismo.
    if path == Path(__file__).resolve():
        continue
    for name, pattern in PATTERNS.items():
        if pattern.search(text):
            findings.append((str(path.relative_to(ROOT)), name))

if findings:
    print("PRIVACY SCAN FAILED")
    for file, kind in findings:
        print(f"- {file}: patrón {kind}")
    sys.exit(1)
print("PRIVACY SCAN OK: no se detectaron secretos o rutas personales de alto riesgo.")
