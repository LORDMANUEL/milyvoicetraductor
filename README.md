# MilyVoiceTraductor

**MilyVoiceTraductor** es una plataforma local para traducir reuniones en inglés o chino a español. La arquitectura separa la aplicación de escritorio, el motor de IA, la extensión Chromium y los pesos de modelos para mantener privacidad, rendimiento y actualización independiente.

> Estado de este paquete: **`1.0.0-rc.1` — implementación completa para validación/pulido final en GitHub**.

## Qué incluye

- **Desktop Tauri 2 + Rust + Svelte/TypeScript**: panel, configuración, SQLite, logs sanitizados, caché, diagnóstico, sesiones y control del motor.
- **Motor IA Python local**: WebSocket autenticado en `127.0.0.1`, PCM16, ASR con faster-whisper, traducción Qwen/NLLB y fallback CPU.
- **Extensión Chromium Manifest V3**: captura explícita de la pestaña, Offscreen Document, AudioWorklet y overlay de subtítulos.
- **Model Manager**: catálogo, descarga a staging, activación atómica, versiones y rollback.
- **Sesiones opt-in**: TXT/SRT únicamente cuando el usuario habilita persistencia.
- **Instalación Windows**: scripts de runtime, extensión, sidecar y build Tauri/NSIS.
- **Versionado/release**: SemVer, manifiestos de canal, checklist y ausencia deliberada de claves privadas.
- **Landing estática** sin trackers para GitHub Pages.

## Privacidad obligatoria

1. El motor escucha únicamente en loopback (`127.0.0.1`).
2. La extensión requiere un token local de emparejamiento.
3. La captura de pestaña solo comienza tras una acción explícita del usuario.
4. Audio y transcripciones no se escriben en logs.
5. La persistencia de texto está desactivada por defecto.
6. No hay telemetría.
7. Ninguna clave privada, contraseña, PAT o credencial pertenece al repositorio.
8. Los pesos de modelos no se guardan en Git ni dentro del ZIP fuente.

## Arquitectura

```text
Google Meet / Teams Web / Zoom Web
              │
              ▼
      Chromium MV3 Extension
 tabCapture → Offscreen → AudioWorklet
              │ PCM16 / WebSocket + token
              ▼
      AI Engine local (Python)
  buffer → faster-whisper → translator
              │
       Qwen3 o NLLB
              │
              ▼
       Español + sesiones

Desktop Tauri 2 / Rust
 ├─ EngineProcessManager
 ├─ ModelManagerService
 ├─ SessionService
 ├─ SQLite
 ├─ configuración
 ├─ caché
 ├─ logs sanitizados
 └─ UI Svelte/TypeScript
```

Más detalle: [`docs/architecture/COMPLETE_ARCHITECTURE.md`](docs/architecture/COMPLETE_ARCHITECTURE.md).

## Estructura

```text
apps/desktop/        Desktop Tauri/Svelte
apps/extension/      Add-on Chromium MV3
apps/site/           Landing GitHub Pages
crates/              Servicios Rust segmentados
services/ai/         Motor IA Python
installer/windows/   Setup/build Windows
resources/           Catálogo de modelos y contratos update
docs/                Arquitectura, privacidad, modelos y release
scripts/             Guardias, tests y empaquetado
```

## Instalación rápida desde fuente en Windows

PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\installer\windows\setup-source.ps1 -InstallPythonIfMissing -ModelPack business-qwen
```

Luego compile/abra el desktop o instale la extensión preparada. Consulte [`docs/INSTALLATION.md`](docs/INSTALLATION.md).

### Extensión

```powershell
.\installer\windows\install-extension.ps1
```

Después cargue `%LOCALAPPDATA%\MilyVoiceTraductor\extension` desde `chrome://extensions` o `edge://extensions` con **Modo desarrollador → Cargar descomprimida**.

## Modelos

El ZIP no contiene pesos de varios GB. El Model Manager los descarga bajo `%LOCALAPPDATA%\MilyVoiceTraductor\models`.

| Pack | Traducción | Perfil |
|---|---|---|
| `business-qwen` | Qwen3 0.6B | **recomendado**; ASR MIT + traductor Apache-2.0, con snapshots fijados por commit |
| `lite-nllb` | NLLB 600M | investigación / **no comercial** por CC-BY-NC-4.0; snapshots fijados por commit |

Consulte [`docs/MODELS.md`](docs/MODELS.md).

## Desarrollo

Requisitos principales: Node.js 22+, Rust estable, Python 3.13 y WebView2/C++ Build Tools en Windows.

```bash
npm install
npm run typecheck
npm test
npm run build
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
```

Motor IA:

```bash
cd services/ai
python -m unittest discover -s tests -p "test_*.py"
python main.py diagnose
```

## Verificación offline antes de subir

```bash
python scripts/verify_source.py
```

Comprueba pruebas Python, privacidad, landing, extensión, sintaxis JS, JSON, catálogo de modelos, placeholders, secretos y archivos demasiado grandes.

## Empaquetar

```bash
python scripts/build_extension_zip.py
python scripts/package_source.py
```

## Releases y actualizaciones

El código del release está preparado para builds NSIS y sidecar. Los artefactos públicos deben firmarse fuera del repositorio; **el ZIP nunca incluye claves privadas**. Consulte [`docs/UPDATES.md`](docs/UPDATES.md) y [`docs/release/RELEASE_CHECKLIST.md`](docs/release/RELEASE_CHECKLIST.md).

## Estado por fase

| Fase | Estado en `1.0.0-rc.1` |
|---|---|
| 1 · Desktop/Rust/SQLite/logs/caché | Implementada |
| 2 · Motor IA/protocolo/CPU-GPU | Implementada |
| 3 · Extensión Chromium/subtítulos | Implementada |
| 4 · Model Manager/versiones/rollback | Implementada |
| 5 · Instalación/build/versionado/release | Implementada como flujo de fuente/release candidate; firma y endpoint público se configuran al publicar |

La siguiente ronda en GitHub es de **CI multiplataforma, empaquetado firmado, medición de latencia y pulido**, no de reconstruir el esqueleto.

## GitHub Pages

La landing está en `apps/site/`. El repositorio necesita tener Pages habilitado con Source = **GitHub Actions** para que el workflow la publique.

## Seguridad

Consulte [`SECURITY.md`](SECURITY.md) y [`docs/privacy/PRIVACY.md`](docs/privacy/PRIVACY.md). No publique audio, transcripciones, credenciales ni diagnósticos sin revisar.

## Licencia

El código de MilyVoiceTraductor usa MIT. Cada modelo conserva su propia licencia y no se redistribuye como parte del ZIP fuente.
