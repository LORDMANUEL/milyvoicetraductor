# Promotional README & Verified Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Presentar MilyVoiceTraductor como producto y publicar descargas RC1 permanentes únicamente desde builds que hayan pasado CI.

**Architecture:** El CI existente sigue siendo la autoridad de build y pruebas. Un workflow `workflow_run` consume el artefacto del CI exitoso en `main`, verifica los hashes y publica los assets en la Release `v1.0.0-rc.1`. README y landing apuntan a esos assets permanentes.

**Tech Stack:** GitHub Actions, GitHub CLI en runner hospedado, Markdown, HTML estático, Python 3.

## Global Constraints

- No publicar una Release desde una rama de desarrollo ni desde un CI fallido.
- No regenerar el instalador en el workflow de publicación.
- Verificar `SHA256SUMS.txt` antes de publicar.
- Mantener el tag de esta RC en `v1.0.0-rc.1`.
- Mantener los nombres exactos de los tres assets publicados.
- Mantener el README orientado a usuario final; la documentación técnica queda enlazada al final.

---

### Task 1: README promocional

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: assets de Release bajo `v1.0.0-rc.1`.
- Produces: enlaces públicos de descarga para Windows, Chromium y SHA-256.

- [ ] Reemplazar la portada técnica por logo, propuesta de valor y botones de descarga.
- [ ] Explicar beneficios, privacidad, compatibilidad, inicio rápido y estado RC sin jerga de implementación.
- [ ] Mantener enlaces a documentación técnica y licencia al final.

### Task 2: Publicación automática de Release verificada

**Files:**
- Create: `.github/workflows/publish-rc.yml`
- Create: `docs/release/RELEASE_NOTES_RC1.md`

**Interfaces:**
- Consumes: workflow `CI` exitoso sobre `main` y artefacto `MilyVoiceTraductor-Full-RC1-Windows-x64-<SHA>`.
- Produces: Release `v1.0.0-rc.1` con instalador, extensión y `SHA256SUMS.txt`.

- [ ] Configurar `workflow_run` para ejecutarse tras CI.
- [ ] Restringir publicación a `conclusion == success` y `head_branch == main`.
- [ ] Descargar el artefacto exacto del run que disparó el workflow.
- [ ] Ejecutar `sha256sum -c SHA256SUMS.txt`.
- [ ] Crear la Release si no existe o actualizar sus assets con `--clobber` si ya existe.

### Task 3: Landing alineada con las descargas

**Files:**
- Modify: `apps/site/index.html`
- Modify: `scripts/test_site.py`

**Interfaces:**
- Consumes: las mismas URLs de Release del README.
- Produces: CTA de descarga coherente y prueba estática de regresión.

- [ ] Cambiar el CTA principal del hero a descarga Windows y agregar descarga Chromium.
- [ ] Cambiar el CTA final a descarga Windows.
- [ ] Hacer que `scripts/test_site.py` falle si desaparece cualquiera de los dos enlaces RC1.

### Task 4: Verificación y entrega

**Files:**
- Verify all modified files.

**Interfaces:**
- Consumes: CI y workflow de publicación.
- Produces: `main` con README comercial y Release descargable.

- [ ] Ejecutar CI en la rama y confirmar todos los jobs verdes.
- [ ] Abrir PR contra `main` y fusionar solo el SHA validado.
- [ ] Confirmar CI verde en `main`.
- [ ] Confirmar que `Publish RC` crea/actualiza `v1.0.0-rc.1`.
- [ ] Comprobar por API que los tres assets aparecen en la Release.
