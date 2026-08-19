#!/usr/bin/env python3
"""Prueba estática sin dependencias para la landing pública de GitHub Pages.

La página puede mostrar solo el canal estable o, durante el desarrollo, el canal
estable junto a Engine Hub beta. En ambos casos conserva producto, privacidad,
descarga estable y versión vigente sin acoplarse a una frase promocional exacta.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
index = ROOT / "apps" / "site" / "index.html"
styles = ROOT / "apps" / "site" / "styles.css"
logo = ROOT / "apps" / "site" / "assets" / "logo.svg"

WINDOWS_DOWNLOAD = "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.1/MilyVoiceTraductor_2.0.1_x64-setup.exe"

errors: list[str] = []
if not index.exists():
    errors.append("Falta apps/site/index.html")
else:
    html = index.read_text(encoding="utf-8")
    for required in [
        "MilyVoiceTraductor",
        "2.0.1",
        'id="producto"',
        'id="privacidad"',
        'id="compute"',
        'id="estado"',
        "Sin telemetría",
        "MilyCompute",
        "Runtime privado",
        "Extensión Chromium",
        "localhost",
        WINDOWS_DOWNLOAD,
    ]:
        if required not in html:
            errors.append(f"Falta contenido requerido: {required}")

    # Cuando se anuncia la beta, debe quedar inequívocamente separada del canal
    # estable y documentar el presupuesto de memoria solicitado por el producto.
    if 'id="beta"' in html:
        for required in (
            "Engine Hub",
            "beta en pruebas",
            "rama <code>pruebas</code>",
            "2 GiB",
            "La versión recomendada sigue siendo 2.0.1",
        ):
            if required not in html:
                errors.append(f"Beta pública incompleta: falta {required}")

    for stale in [
        "2.0 RC",
        "Candidata actual",
        "permanece RC",
        "releases/download/v2.0.0/",
        "2.0.0 · Runtime privado",
    ]:
        if stale in html:
            errors.append(f"Contenido obsoleto prohibido: {stale}")

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
print("SITE CHECK OK: producto 2.0.1, privacidad, MilyCompute y canales estable/beta coherentes.")
