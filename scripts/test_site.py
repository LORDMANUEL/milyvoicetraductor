#!/usr/bin/env python3
"""Prueba estática sin dependencias para la landing pública de GitHub Pages."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
index = ROOT / "apps" / "site" / "index.html"
styles = ROOT / "apps" / "site" / "styles.css"
logo = ROOT / "apps" / "site" / "assets" / "logo.svg"
history = ROOT / "docs" / "release" / "VERSION_HISTORY.md"

WINDOWS_DOWNLOAD = "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor_2.0.1_x64-setup.exe"
HISTORICAL_DOWNLOADS = [
    "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.0/MilyVoiceTraductor_2.0.0_x64-setup.exe",
    "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.5/MilyVoiceTraductor_1.0.5_x64-setup.exe",
    "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.0-rc.1/MilyVoiceTraductor_1.0.0-rc.1_x64-setup.exe",
]

errors: list[str] = []
if not index.exists():
    errors.append("Falta apps/site/index.html")
else:
    html = index.read_text(encoding="utf-8")
    for required in [
        "MilyVoiceTraductor 2.0.1",
        'id="privacidad"',
        'id="compute"',
        'id="beta"',
        'id="versiones"',
        'id="estado"',
        "Sin telemetría",
        "MilyCompute",
        "MegaBench",
        "2.0.1 · Runtime privado",
        "Engine Hub",
        "BetaAlpha",
        "1.0.0 RC1",
        "MilyVoiceTraductor 1.0.5",
        "MilyVoiceTraductor 2.0.0",
        WINDOWS_DOWNLOAD,
        "https://github.com/LORDMANUEL/milyvoicetraductor/tree/pruebas",
        "https://github.com/LORDMANUEL/milyvoicetraductor/tree/betaalpha",
    ] + HISTORICAL_DOWNLOADS:
        if required not in html:
            errors.append(f"Falta contenido requerido: {required}")

    for stale in [
        "2.0 RC",
        "Candidata actual",
        "permanece RC",
    ]:
        if stale in html:
            errors.append(f"Contenido obsoleto prohibido: {stale}")

    lowered = html.lower()
    for forbidden in ["google-analytics", "googletagmanager", "facebook.net", "segment.com"]:
        if forbidden in lowered:
            errors.append(f"Tracker externo prohibido: {forbidden}")

for asset in [styles, logo, history]:
    if not asset.exists():
        errors.append(f"Falta asset/registro: {asset.relative_to(ROOT)}")

if history.exists():
    registry = history.read_text(encoding="utf-8")
    for required in [
        "v1.0.0-rc.1",
        "v1.0.5",
        "v2.0.0",
        "v2.0.1",
        "875c182c67bcc4c2984cf15de474602017129f99",
        "1da9a1090535f8f69639c7def2cc760e4b76364d",
    ]:
        if required not in registry:
            errors.append(f"Falta en VERSION_HISTORY.md: {required}")

if errors:
    print("SITE CHECK FAILED")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)
print("SITE CHECK OK: estable 2.0.1, historial 1.0.0-rc.1/1.0.5/2.0.0, Engine Hub y BetaAlpha presentes.")