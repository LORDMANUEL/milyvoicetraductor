# MilyVoiceTraductor

**MilyVoiceTraductor** es una plataforma local de traducción de voz para reuniones, diseñada para convertir audio en inglés o chino a español sin enviar el contenido de la reunión a servicios externos.

> Estado actual: **Fase 1 — Fundación de escritorio (`0.1.0`)**.

## Objetivo

El proyecto está diseñado para terminar ofreciendo:

- captura de audio desde reuniones en navegadores Chromium;
- reconocimiento de voz local;
- traducción local inglés/chino → español;
- subtítulos en vivo;
- funcionamiento en CPU y aceleración opcional por GPU;
- historial y exportación controlados por el usuario;
- actualización independiente de aplicación, motor y modelos.

La Fase 1 construye la base segura: aplicación Tauri, backend Rust modular, UI Svelte, configuración persistente, SQLite, logs sanitizados, caché limitada y diagnóstico del equipo. **Todavía no ejecuta modelos ni captura audio.**

## Principios del proyecto

1. **Privacidad por defecto:** no hay telemetría ni servicios cloud obligatorios.
2. **Sin secretos en Git:** tokens, claves, credenciales y datos privados están prohibidos.
3. **Logs seguros:** nunca deben contener audio, transcripciones, correos, tokens ni rutas personales completas.
4. **Ligero:** Tauri/Rust para evitar incluir un runtime de navegador completo.
5. **CPU-first:** una GPU nunca es requisito para abrir o administrar la aplicación.
6. **Estados reales:** una función no implementada se muestra como no instalada, no como éxito simulado.
7. **Código segmentado:** cada crate, servicio y componente tiene una responsabilidad concreta.

## Arquitectura

```text
Svelte 5 + TypeScript
        │
        │ invoke()
        ▼
Tauri 2 / Rust
        │
        ├─ mily-core       contratos y DTOs
        ├─ mily-config     rutas y configuración
        ├─ mily-database   SQLite + migraciones
        ├─ mily-logging    logs sanitizados y rotación
        ├─ mily-cache      caché limitada y expirable
        └─ mily-system     información CPU/RAM/SO

Fase 2 ──> motor IA local (sidecar)
Fase 3 ──> extensión Chromium
Fase 4 ──> gestor/versionado de modelos
```

## Estructura

```text
apps/desktop/       Aplicación Tauri + Svelte
apps/site/          Web estática para GitHub Pages
crates/             Servicios Rust independientes
packages/brand/     Tokens visuales compartidos
docs/               Arquitectura, privacidad y planes
scripts/            Pruebas/controles de repositorio
.github/workflows/  CI y despliegue Pages
```

## Requisitos de desarrollo

### Windows

- Node.js 22 LTS o superior compatible.
- Rust estable con toolchain `stable-msvc`.
- Microsoft C++ Build Tools.
- WebView2, normalmente incluido en Windows moderno.

Tauri mantiene la guía oficial de prerrequisitos en su documentación.

### Instalar frontend

```bash
npm install
```

### Ejecutar interfaz web

```bash
npm run dev
```

### Ejecutar aplicación Tauri

```bash
npm run tauri -- dev
```

### Pruebas

```bash
npm test
cargo test --workspace
python3 scripts/test_site.py
python3 scripts/privacy_scan.py .
```

### Calidad Rust

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
```

## Datos locales

La aplicación crea sus datos mediante las rutas estándar del sistema operativo. Los módulos separan:

- configuración;
- base de datos;
- logs;
- caché.

La caché contiene únicamente información regenerable. Los logs pasan por sanitización antes de escribirse.

## GitHub Pages

La landing page vive en `apps/site/` y se despliega con GitHub Actions al publicar cambios en `main`.

URL esperada del proyecto:

`https://lordmanuel.github.io/milyvoicetraductor/`

La web no incorpora Google Analytics, píxeles, cookies de seguimiento ni JavaScript de terceros.

## Fases

| Fase | Estado | Alcance |
|---|---|---|
| 1 | En desarrollo | Tauri/Rust/Svelte, persistencia, logs, caché, diagnóstico, web |
| 2 | Pendiente | Motor IA local y protocolo |
| 3 | Pendiente | Extensión Chromium y captura de pestaña |
| 4 | Pendiente | Descarga/versionado/rollback de modelos |
| 5 | Pendiente | Instalador y actualizador firmado |

## Seguridad

Consulta [`SECURITY.md`](SECURITY.md) y [`docs/privacy/PRIVACY.md`](docs/privacy/PRIVACY.md).

No abras issues públicos con credenciales, audio de reuniones, transcripciones, datos personales o archivos de diagnóstico sin revisar.

## Licencia

Código del proyecto: MIT. Los modelos de IA que se integren en fases posteriores conservarán sus propias licencias y se documentarán antes de distribuirse.
