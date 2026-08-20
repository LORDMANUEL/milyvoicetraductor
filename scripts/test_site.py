#!/usr/bin/env python3
"""Prueba estática sin dependencias para la landing pública de GitHub Pages."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
index = ROOT / "apps" / "site" / "index.html"
styles = ROOT / "apps" / "site" / "styles.css"
logo = ROOT / "apps" / "site" / "assets" / "logo.svg"
history = ROOT / "docs" / "release" / "VERSION_HISTORY.md"

CURRENT_VERSION = "2.1.0"
CURRENT_INSTALLER = (
    "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/"
    "v2.1.0/MilyVoiceTraductor_2.1.0_x64-setup.exe"
)
CURRENT_EXTENSION = (
    "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/"
    "v2.1.0/MilyVoiceTraductor-Chromium-Extension.zip"
)
CURRENT_RELEASE = "https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.1.0"

errors: list[str] = []
if not index.exists():
    errors.append("Falta apps/site/index.html")
else:
    html = index.read_text(encoding="utf-8")
    required_content = [
        f"MilyVoiceTraductor {CURRENT_VERSION}",
        "2.1.0 ESTABLE",
        'id="privacidad"',
        'id="compute"',
        'id="versiones"',
        'id="estado"',
        "Sin telemetría",
        "MilyCompute",
        "Engine Hub",
        "Moonshine",
        "Whisper Tiny",
        "Sherpa Zipformer",
        "MilyVoiceTraductor 2.0.1",
        "MilyVoiceTraductor 2.0.0",
        CURRENT_INSTALLER,
        CURRENT_EXTENSION,
        CURRENT_RELEASE,
    ]
    for required in required_content:
        if required not in html:
            errors.append(f"Falta contenido requerido: {required}")

    for stale in [
        "Descargar estable 2.0.1",
        "La versión recomendada sigue siendo 2.0.1",
        "2.0.1 estable · Engine Hub Beta · BetaAlpha",
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
        "v2.1.0",
        "6645be5413a46d92e24b0c37c56b1bb851a94067",
        "v2.0.1",
        "v2.0.0",
        "v1.0.5",
        "v1.0.0-rc.1",
        "875c182c67bcc4c2984cf15de474602017129f99",
        "1da9a1090535f8f69639c7def2cc760e4b76364d",
    ]:
        if required not in registry:
            errors.append(f"Falta en VERSION_HISTORY.md: {required}")

if errors:
    print("SITE CHECK FAILED")
    for error in errors:
        print("-", error)
    sys.exit(1)
print(
    "SITE CHECK OK: estable 2.1.0, historial de releases, "
    "Engine Hub y evidencias de plataforma presentes."
)
