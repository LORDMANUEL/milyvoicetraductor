# Automatic Onboarding & Embedded Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir MilyVoiceTraductor en un flujo de instalación simple donde desktop y extensión se autoreconocen, el runtime IA viene incluido en la distribución y la preparación de modelos expone progreso y errores reales.

**Architecture:** `main` queda reservado para releases; `pruebas` concentra desarrollo y CI. El instalador Windows incluye el runtime IA preparado en CI y un bridge nativo Rust registrado como Native Messaging Host. La extensión usa Native Messaging para descubrir la app y obtener una credencial efímera/puerto; el audio continúa viajando únicamente por WebSocket loopback. La descarga de modelos se realiza desde la app, fuera de NSIS, con diagnóstico estructurado.

**Tech Stack:** Tauri 2, Rust 2024, Svelte 5, TypeScript, Chromium Manifest V3 + Native Messaging, Python 3.13 privado, FastAPI/WebSocket, faster-whisper, Hugging Face Hub, NSIS, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-17-automatic-onboarding-embedded-runtime-design.md`

## Global Constraints

- Solo `main` y `pruebas` se usan para trabajo activo.
- Sin `winget`, Python del sistema ni `pip install` online durante instalación normal.
- Sin token o puerto visibles en la experiencia normal de la extensión.
- Motor restringido a `127.0.0.1`.
- Native Messaging con `allowed_origins` explícitos.
- Audio no viaja por Native Messaging.
- Modelos permanecen fuera del EXE y se descargan con staging, reanudación y activación atómica.
- Los errores públicos de modelos deben conservar código estable y mensaje concreto.
- Sin telemetría y sin contenido de reunión en logs.

---

### Task 1: Diagnóstico estructurado del Model Manager

**Files:**
- Modify: `crates/mily-models/src/lib.rs`
- Modify: `apps/desktop/src-tauri/src/commands/mod.rs`
- Modify: `apps/desktop/src/types.ts`
- Modify: `apps/desktop/src/pages/Models.svelte`
- Test: `crates/mily-models/src/lib.rs`

**Interfaces:**
- Produces: `ModelOperationError { code, message }` and public `PublicError.code` mappings such as `MODEL_RUNTIME_ERROR`, `MODEL_NO_NETWORK`, `MODEL_NO_SPACE`, `MODEL_PROVIDER_ERROR`, `MODEL_HASH_MISMATCH`.

- [ ] Write a Rust unit test proving a non-zero engine CLI exit with stderr containing a structured JSON error maps to the exact public code instead of `InstallFailed`.
- [ ] Replace `stdout(Stdio::null())/stderr(Stdio::null())` with captured output and structured parsing.
- [ ] Preserve sanitized diagnostic text in logs while returning only safe code/message to UI.
- [ ] Update `Models.svelte` to render exact recovery text per code and a `Reintentar` action.
- [ ] Run `cargo test -p mily-models` and frontend tests.

### Task 2: Native Messaging bridge in Rust

**Files:**
- Create: `crates/mily-bridge/Cargo.toml`
- Create: `crates/mily-bridge/src/main.rs`
- Create: `crates/mily-bridge/src/protocol.rs`
- Create: `crates/mily-bridge/src/runtime.rs`
- Modify: `Cargo.toml`
- Test: `crates/mily-bridge/src/protocol.rs`

**Interfaces:**
- Consumes: `AppPaths`, `EngineProcessManager`, model `current.json`.
- Produces Native Messaging replies:
  `{"protocol":1,"type":"bridge.ready","engine":"ready|stopped|notInstalled","port":8765,"credential":"...","expiresAt":<unix>,"modelPack":"..."}`.

- [ ] Write tests for 32-bit little-endian Native Messaging framing and rejection of oversized messages.
- [ ] Implement stdin/stdout framing with a 1 MiB request cap.
- [ ] Implement `hello` command that ensures the engine is started and returns a short-lived credential.
- [ ] Implement `status` command without exposing paths or persistent secrets.
- [ ] Add bridge crate to workspace and build tests.

### Task 3: Ephemeral credentials in the local engine

**Files:**
- Modify: `services/ai/mily_ai/security.py`
- Modify: `services/ai/mily_ai/server.py`
- Create: `services/ai/tests/test_ephemeral_credentials.py`

**Interfaces:**
- Produces: credential file under private config with `token`, `expiresAt`, consumed by WebSocket auth.

- [ ] Write failing tests for accepted valid credential and rejection after expiration.
- [ ] Add atomic ephemeral credential store with maximum 5 minute lifetime.
- [ ] Make WebSocket accept either the current ephemeral credential or an internal desktop token for backward-compatible diagnostics.
- [ ] Ensure logs never serialize either token.
- [ ] Run Python test suite.

### Task 4: Extension auto-discovery

**Files:**
- Modify: `apps/extension/manifest.json`
- Modify: `apps/extension/background.js`
- Modify: `apps/extension/popup.html`
- Modify: `apps/extension/popup.js`
- Modify: `apps/extension/popup.css`
- Modify: `apps/extension/offscreen.js`
- Modify: `scripts/test_extension.py`

**Interfaces:**
- Consumes: `chrome.runtime.connectNative("com.milyvoice.traductor")`.
- Removes: user-managed `pairingToken`, `enginePort`.

- [ ] Extend static test to require `nativeMessaging` and prohibit token/port input fields in popup.
- [ ] Add native host connection/reconnect in background service worker.
- [ ] Cache bridge state only in `chrome.storage.session`, never persistent secrets.
- [ ] Pass ephemeral credential and discovered port to offscreen capture.
- [ ] Replace popup with detected-state UI and one `Iniciar traducción` action.
- [ ] Run `node --check` and extension guard.

### Task 5: Windows Native Messaging registration

**Files:**
- Create: `installer/windows/native-host-template.json`
- Create: `installer/windows/register-native-host.ps1`
- Modify: `apps/desktop/src-tauri/tauri.conf.json`
- Modify: `apps/desktop/src-tauri/windows/hooks.nsh`
- Modify: `scripts/verify_source.py`

**Interfaces:**
- Registers host `com.milyvoice.traductor` in HKCU for Chrome and Chromium-family browsers supported by the installer.

- [ ] Add source guard that fails if host manifest has wildcard origins.
- [ ] Generate manifest with bridge absolute path and exact extension origin placeholder resolved by release packaging.
- [ ] Register/unregister keys idempotently.
- [ ] Bundle bridge executable and host manifest in NSIS resources.
- [ ] Validate PowerShell syntax in Windows CI.

### Task 6: Prebuilt private Python runtime

**Files:**
- Create: `installer/windows/build-python-runtime.ps1`
- Modify: `installer/windows/setup-installed.ps1`
- Modify: `.github/workflows/ci.yml`
- Modify: `apps/desktop/src-tauri/tauri.conf.json`

**Interfaces:**
- Produces `dist/runtime/python/` with `python.exe`, engine package and frozen runtime dependencies before NSIS runs.

- [ ] Add a Windows CI test that fails if installer script contains `winget install` or runtime `pip install`.
- [ ] Build Python 3.13 private runtime during CI and install dependencies into staging before bundling.
- [ ] Generate runtime manifest SHA-256.
- [ ] Change setup script to copy/verify staged runtime only.
- [ ] Bundle staged runtime into NSIS.
- [ ] Run a smoke command from staged Python: `python engine/main.py diagnose`.

### Task 7: Onboarding and automatic model preparation

**Files:**
- Create: `apps/desktop/src/pages/Onboarding.svelte`
- Modify: `apps/desktop/src/App.svelte`
- Modify: `apps/desktop/src/lib/api.ts`
- Modify: `apps/desktop/src-tauri/src/commands/mod.rs`
- Modify: `crates/mily-models/src/lib.rs`

**Interfaces:**
- Produces: onboarding state `runtimeReady`, `bridgeReady`, `extensionDetected`, `modelState`, `downloadedBytes`, `totalBytes`, `errorCode`.

- [ ] Write frontend test for first-run auto-onboarding when no active model exists.
- [ ] Add desktop command returning consolidated readiness state.
- [ ] Start model preparation automatically for `business-qwen` after runtime is ready.
- [ ] Show download progress and keep UI usable while task runs.
- [ ] Add retry without deleting valid partial cache.
- [ ] Route success directly to `Traducción en vivo`.

### Task 8: Installer UX and recovery

**Files:**
- Modify: `apps/desktop/src-tauri/windows/hooks.nsh`
- Modify: `installer/windows/setup-installed.ps1`
- Create: `installer/windows/test-bootstrap.ps1`

**Interfaces:**
- NSIS installs files/registration only; it no longer downloads model weights.

- [ ] Add regression test that setup succeeds with network unavailable because model download is not part of setup.
- [ ] Remove Python discovery, `winget`, online pip and model download from NSIS post-install.
- [ ] Verify runtime manifest and Native Messaging registration.
- [ ] Launch desktop after successful install.
- [ ] Persist a recoverable bootstrap status with stage/code only, no personal paths/secrets.

### Task 9: CI, release and branch policy

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/publish-rc.yml`
- Modify: `README.md`
- Modify: `apps/site/index.html`

**Interfaces:**
- Active branches: `main`, `pruebas` only.

- [ ] Configure CI pushes for `main` and `pruebas` only.
- [ ] Build/test embedded runtime, bridge, extension, desktop and NSIS on Windows.
- [ ] Keep release publication restricted to successful `main` CI.
- [ ] Update product copy to explain auto-recognition and zero manual pairing.
- [ ] After `pruebas` passes, fast-forward/merge to `main`, verify final CI, then delete obsolete branches.
