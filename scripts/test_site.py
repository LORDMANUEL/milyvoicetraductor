#!/usr/bin/env python3
"""Prueba estática sin dependencias para la landing pública de GitHub Pages."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
index = ROOT / "apps" / "site" / "index.html"
styles = ROOT / "apps" / "site" / "styles.css"
logo = ROOT / "apps" / "site" / "assets" / "logo.svg"
history = ROOT / "docs" / "release" / "VERSION_HISTORY.md"
release_status = ROOT / "apps" / "site" / "release-status.json"
stable_notes = ROOT / "docs" / "release" / "RELEASE_NOTES_2.0.2.md"

STABLE_VERSION = "2.0.2"
BETA_VERSION = "2.1.0"
STABLE_INSTALLER = (
    "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/"
    "v2.0.2/MilyVoiceTraductor_2.0.2_x64-setup.exe"
)
STABLE_EXTENSION = (
    "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/"
    "v2.0.2/MilyVoiceTraductor-Chromium-Extension.zip"
)
STABLE_RELEASE = "https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.2"
BETA_INSTALLER = (
    "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/"
    "v2.1.0/MilyVoiceTraductor_2.1.0_x64-setup.exe"
)
BETA_EXTENSION = (
    "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/"
    "v2.1.0/MilyVoiceTraductor-Chromium-Extension.zip"
)
BETA_RELEASE = "https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.1.0"
HISTORICAL_DOWNLOADS = [
    "https://github.com/LORDMANUEL/milyvoicetraductor/releases/tag/v2.0.1",
    "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v2.0.0/MilyVoiceTraductor_2.0.0_x64-setup.exe",
    "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.5/MilyVoiceTraductor_1.0.5_x64-setup.exe",
    "https://github.com/LORDMANUEL/milyvoicetraductor/releases/download/v1.0.0-rc.1/MilyVoiceTraductor_1.0.0-rc.1_x64-setup.exe",
]

errors: list[str] = []
if not index.exists():
    errors.append("Falta apps/site/index.html")
else:
    html = index.read_text(encoding="utf-8")
    required_content = [
        "2.0.2 ESTABLE",
        "2.1.0 BETA",
        "MilyVoiceTraductor 2.0.2",
        "MilyVoiceTraductor 2.1.0 Beta",
        'id="privacidad"',
        'id="compute"',
        'id="beta"',
        'id="versiones"',
        'id="estado"',
        "Sin telemetría",
        "MilyCompute",
        "Engine Hub",
        "MegaBench",
        "Moonshine",
        "Whisper Tiny",
        "Sherpa Zipformer",
        "BetaAlpha",
        "MilyVoiceTraductor 2.0.1",
        "MilyVoiceTraductor 2.0.0",
        "MilyVoiceTraductor 1.0.5",
        "MilyVoiceTraductor 1.0.0 RC1",
        STABLE_INSTALLER,
        STABLE_RELEASE,
        BETA_INSTALLER,
        BETA_EXTENSION,
        BETA_RELEASE,
        "https://github.com/LORDMANUEL/milyvoicetraductor/tree/pruebas",
        "https://github.com/LORDMANUEL/milyvoicetraductor/tree/betaalpha",
    ] + HISTORICAL_DOWNLOADS
    for required in required_content:
        if required not in html:
            errors.append(f"Falta contenido requerido: {required}")

    for stale in [
        "2.1.0 ESTABLE",
        "Descargar estable 2.1.0",
        "La versión estable recomendada es v2.1.0",
        "La descarga estable ya es 2.1.0",
        "2.0.1 ESTABLE",
        "Descargar estable 2.0.1",
        "La versión recomendada sigue siendo 2.0.1",
        "2.0 RC",
        "Candidata actual",
        "permanece RC",
    ]:
        if stale in html:
            errors.append(f"Contenido obsoleto/prohibido: {stale}")

    lowered = html.lower()
    for forbidden in ["google-analytics", "googletagmanager", "facebook.net", "segment.com"]:
        if forbidden in lowered:
            errors.append(f"Tracker externo prohibido: {forbidden}")

for asset in [styles, logo, history, release_status, stable_notes]:
    if not asset.exists():
        errors.append(f"Falta asset/registro: {asset.relative_to(ROOT)}")

if release_status.exists():
    payload = json.loads(release_status.read_text(encoding="utf-8"))
    stable = payload.get("stable", {})
    beta = payload.get("beta", {})
    if stable.get("version") != STABLE_VERSION or stable.get("channel") != "stable" or stable.get("recommended") is not True:
        errors.append("release-status.json: canal estable no apunta a 2.0.2 recomendado")
    if stable.get("installer") != STABLE_INSTALLER:
        errors.append("release-status.json: instalador estable incorrecto")
    if stable.get("extension") != STABLE_EXTENSION or stable.get("release") != STABLE_RELEASE:
        errors.append("release-status.json: assets/release estable incorrectos")
    if beta.get("version") != BETA_VERSION or beta.get("channel") != "beta" or beta.get("recommended") is not False:
        errors.append("release-status.json: canal beta no apunta a 2.1.0")

if history.exists():
    registry = history.read_text(encoding="utf-8")
    for required in [
        "v2.0.2",
        "Estable actual",
        "cfd3946644c41242e6345c2c593f4edb7a1047b4",
        "v2.0.1",
        "Histórica estable",
        "v2.1.0",
        "Beta pública",
        "v2.0.0",
        "v1.0.5",
        "v1.0.0-rc.1",
        "6645be5413a46d92e24b0c37c56b1bb851a94067",
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
    "SITE CHECK OK: 2.0.2 estable, 2.1.0 beta, historial y referencias de I+D presentes."
)
