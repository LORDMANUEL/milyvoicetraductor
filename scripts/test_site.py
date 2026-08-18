#!/usr/bin/env python3
"""Prueba estática sin dependencias para la landing de GitHub Pages."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
index = ROOT / "apps" / "site" / "index.html"
styles = ROOT / "apps" / "site" / "styles.css"
logo = ROOT / "apps" / "site" / "assets" / "logo.svg"

WINDOWS_DOWNLOAD = "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.5/MilyVoiceTraductor_1.0.5_x64-setup.exe"
CHROMIUM_DOWNLOAD = "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.5/MilyVoiceTraductor-Chromium-Extension.zip"

errors: list[str] = []
if not index.exists():
    errors.append("Falta apps/site/index.html")
else:
    html = index.read_text(encoding="utf-8")
    for required in [
        "MilyVoiceTraductor",
        'id="privacidad"',
        'id="arquitectura"',
        'id="estado"',
        "Sin telemetría",
        "MilyVoiceTraductor 1.0.5",
        WINDOWS_DOWNLOAD,
        CHROMIUM_DOWNLOAD,
    ]:
        if required not in html:
            errors.append(f"Falta contenido requerido: {required}")
    lowered = html.lower()
    for forbidden in ["google-analytics", "googletagmanager", "facebook.net", "segment.com"]:
        if forbidden in lowered:
            errors.append(f"Tracker externo prohibido: {forbidden}")

for asset in [styles, logo]:
    if not asset.exists():
        errors.append(f"Falta asset: {asset.relative_to(ROOT)}")

if errors:
    print("SITE CHECK FAILED")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)
print("SITE CHECK OK: branding, privacidad y descargas 1.0.5 presentes.")
