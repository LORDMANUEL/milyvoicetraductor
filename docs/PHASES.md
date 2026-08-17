# Estado de fases — MilyVoiceTraductor 1.0.0-rc.1

Esta release candidate se considera **feature-complete a nivel de fuente**. La publicación estable `1.0.0` exige ejecutar CI con Rust/Tauri/Svelte y una prueba E2E en Windows con modelos reales descargados.

| Fase | Estado RC | Entregable |
|---|---|---|
| 1. Fundación | Completa | Tauri 2, Rust modular, Svelte, SQLite, configuración, logs, caché, diagnóstico y branding. |
| 2. Motor IA | Completa en fuente | FastAPI/WebSocket localhost, PCM16, faster-whisper, Qwen/NLLB, CPU/GPU opcional, token local y tests de servidor. |
| 3. Extensión Chromium | Completa en fuente | Manifest V3, `tabCapture`, Offscreen, AudioWorklet, popup, overlay y permisos mínimos. |
| 4. Model Manager | Completa en fuente | snapshots fijados por commit, staging, activación atómica, SHA-256 local, verificación, rollback y eliminación de packs inactivos. |
| 5. Distribución y actualización | Completa en fuente | scripts Windows, runtime Python aislado, build Nuitka, Tauri/NSIS y contrato de updater firmado. |
| 6. Sesiones | Completa | persistencia opt-in, listado, TXT/SRT y borrado local. |

## Gates antes de `1.0.0` estable

1. CI Linux y Windows: `cargo fmt`, `cargo test`, `clippy`, Svelte typecheck/tests/build y Tauri release build.
2. Descargar el pack `business-qwen` fijado en el catálogo y ejecutar una reunión real en Meet/Teams/Zoom Web.
3. Medir latencia y consumo en CPU sin GPU y en un equipo con CUDA.
4. Generar el instalador NSIS final y validar instalación/desinstalación en una VM Windows limpia.
5. Configurar claves/endpoint del Tauri Updater fuera del repositorio y generar artefactos firmados.

Ninguno de esos gates exige cambiar la arquitectura; son validaciones de publicación sobre el código RC incluido en este paquete.
