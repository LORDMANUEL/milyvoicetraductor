# Tier 1 Bidirectional 2.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer ejecutables EN→ES, ZH→ES, ES→EN y ES→ZH en MilyVoiceTraductor 2.1 sin mezclar full-duplex ni Tutor.

**Architecture:** El protocolo se convierte en la autoridad de ruta; el servidor valida el pack activo contra la ruta solicitada; `RealtimePipeline` y los proveedores reciben el destino real. Desktop y extensión propagan `targetLanguage` extremo a extremo y TTS usa el idioma destino.

**Tech Stack:** Python 3.13, FastAPI/WebSocket, faster-whisper, CTranslate2/M2M100, Svelte/TypeScript, Chromium Manifest V3, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-26-tier1-bidirectional-2.1-design.md`

## Global Constraints

- Rutas permitidas: EN→ES, ZH→ES, ES→EN, ES→ZH.
- `auto` solo puede usarse con destino `es`.
- CPU sigue siendo fallback seguro.
- No ampliar falsamente los packs Lite a rutas no verificadas.
- No cambiar 2.0.2 Stable ni promover 2.1.0 a estable sin CI completo.
- Full-duplex, micrófono virtual y Tutor completo quedan fuera de esta fase.

---

### Task 1: Contrato WebSocket Tier 1

**Files:**
- Modify: `services/ai/mily_ai/protocol.py`
- Modify: `services/ai/tests/test_protocol.py`

**Interfaces:**
- Consumes: `mily_ai.languages.get_tier1_route(source, target)`.
- Produces: `ClientMessage.source_language` y `ClientMessage.target_language` validados para las cuatro rutas.

- [ ] **Step 1: Write the failing tests**

Agregar casos que acepten `es→en`, `es→zh`, mantengan `en→es`, `zh→es`, acepten `auto→es` y rechacen `auto→en`, `en→zh`, `es→es`.

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=services/ai python -m unittest services.ai.tests.test_protocol -v`
Expected: FAIL porque `es` no está en `ALLOWED_SOURCES` y el destino solo acepta `es`.

- [ ] **Step 3: Implement minimal route validation**

En `ClientMessage.parse`, normalizar source/target con `normalize_language`. Aceptar `auto→es`; para el resto exigir `get_tier1_route(source, target) is not None`. Lanzar `ProtocolError("Ruta de idioma no permitida")` fuera del contrato.

- [ ] **Step 4: Verify GREEN**

Run: `PYTHONPATH=services/ai python -m unittest services.ai.tests.test_protocol -v`
Expected: PASS.

---

### Task 2: ASR/MT dinámicos y pack Quality bidireccional

**Files:**
- Modify: `services/ai/mily_ai/providers.py`
- Modify: `services/ai/mily_ai/provider_factory.py`
- Modify: `services/ai/mily_ai/model-packs.json`
- Modify: `services/ai/tests/test_provider_factory.py`
- Create: `services/ai/tests/test_m2m100_target_language.py`

**Interfaces:**
- Produces: `M2M100CTranslate2Translator(..., target_language: str = "es")`.
- Produces: `build_translation_provider(..., target_language: str | None = None)`; para M2M100 usa el destino de sesión, Marian conserva su manifiesto.

- [ ] **Step 1: Write failing tests**

Probar que `build_translation_provider` construye M2M100 con destino `en`/`zh`, que el token de destino usado por `translate()` corresponde a `self.target_language`, y que Faster-Whisper acepta `source_language="es"` sin convertirlo a inglés.

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=services/ai python -m unittest services.ai.tests.test_provider_factory services.ai.tests.test_m2m100_target_language -v`
Expected: FAIL porque M2M100 fija `es` y warm-up/ASR no contempla español.

- [ ] **Step 3: Implement target-aware M2M100 and Spanish ASR**

Guardar `target_language` normalizado en M2M100; usar `lang_code_to_token[self.target_language]`; warm-up con una pareja mínima compatible. En Faster-Whisper incluir `es` en idiomas explícitos/detectados admitidos. Actualizar factory para pasar el destino de sesión solo a M2M100.

- [ ] **Step 4: Expand only Quality pack routes**

Cambiar `realtime-m2m100.routes` a `["en-es","zh-es","es-en","es-zh"]`. No modificar rutas de `fast-moonshine-en-es`, `lite-en-es`, `sherpa-zipformer-en-es` ni `lite-zh-es`.

- [ ] **Step 5: Verify GREEN**

Run: `PYTHONPATH=services/ai python -m unittest services.ai.tests.test_provider_factory services.ai.tests.test_m2m100_target_language services.ai.tests.test_model_pack_v2 -v`
Expected: PASS.

---

### Task 3: Pipeline y servidor conscientes de ruta

**Files:**
- Modify: `services/ai/mily_ai/pipeline.py`
- Modify: `services/ai/mily_ai/server.py`
- Modify: `services/ai/tests/test_pipeline_streaming.py`
- Modify: `services/ai/tests/test_server.py`
- Create: `services/ai/tests/test_tier1_session_route.py`

**Interfaces:**
- Produces: `RealtimePipeline(..., target_language: str = "es", ...)`.
- Server calcula `route_id` y valida `route_id in definition["routes"]` antes de warm-up.

- [ ] **Step 1: Write failing tests**

Probar que pipeline conserva `source_language="es"`, `target_language="en"`; que detección explícita devuelve `es`; y que el servidor devuelve `MODEL_ROUTE_UNSUPPORTED` cuando el pack activo no declara la ruta.

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=services/ai python -m unittest services.ai.tests.test_tier1_session_route -v`
Expected: FAIL porque pipeline no recibe destino y servidor no valida rutas.

- [ ] **Step 3: Implement route propagation**

Añadir `target_language` al pipeline, pasarlo a `build_translation_provider`, usarlo en `SessionRecorder.start`, y permitir `es` en `_detect_language` cuando está configurado. En server validar la ruta del pack antes de crear recorder/pipeline y pasar `message.target_language`.

- [ ] **Step 4: Fix internal engine version drift**

Importar `mily_ai.__version__` en server y usarlo en `/health` y `engine.ready` en lugar de `"2.0.1"` hardcodeado.

- [ ] **Step 5: Verify GREEN**

Run: `PYTHONPATH=services/ai python -m unittest services.ai.tests.test_tier1_session_route services.ai.tests.test_server services.ai.tests.test_pipeline_streaming -v`
Expected: PASS.

---

### Task 4: Desktop target-aware

**Files:**
- Modify: `apps/desktop/src/lib/realtime.ts`
- Modify: `apps/desktop/src/pages/LiveTranslation.svelte`
- Modify: `apps/desktop/src/types.ts`
- Test: existing frontend tests plus a new focused contract test if no realtime test exists.

**Interfaces:**
- `LocalRealtimeClient.connect(sourceLanguage, targetLanguage, ...)`.
- `DesktopAudioCapture.startMicrophone/startSystemAudio/startMediaElement` receive target language.

- [ ] **Step 1: Write failing frontend contract test**

Assert source contains dynamic `targetLanguage` in hello/chunk/stop and LiveTranslation exposes selector with `es`, `en`, `zh`, while incompatible combinations are normalized before start.

- [ ] **Step 2: Verify RED**

Run: `npm run --prefix apps/desktop test -- --run`
Expected: FAIL on hardcoded `targetLanguage: 'es'`.

- [ ] **Step 3: Implement dynamic route and TTS locale**

Track `targetLanguage: 'es'|'en'|'zh'`. Enforce: target `en|zh` ⇒ source `es`; source `auto|en|zh` ⇒ target `es`. Propagate destination through capture/client. Replace `speakSpanish` with target-aware TTS mapping `es→es-ES`, `en→en-US`, `zh→zh-CN` and filter voices by target prefix.

- [ ] **Step 4: Verify GREEN**

Run: `npm run --prefix apps/desktop typecheck && npm run --prefix apps/desktop test -- --run && npm run --prefix apps/desktop build`
Expected: PASS.

---

### Task 5: Extension target-aware

**Files:**
- Modify: `apps/extension/popup.html`
- Modify: `apps/extension/popup.js`
- Modify: `apps/extension/background.js`
- Modify: `apps/extension/offscreen.js`
- Modify: `apps/extension/tts.js`
- Modify/Create: extension contract tests under `services/ai/tests/`.

**Interfaces:**
- Popup stores `targetLanguage`.
- Background passes it to offscreen/capture state.
- Offscreen sends it in hello/chunk/stop/control messages.
- `speakTranslation` reads target language and selects locale.

- [ ] **Step 1: Write failing static contract tests**

Assert popup destination is selectable, `targetLanguage` persists, and no capture path hardcodes Spanish as destination. Assert TTS maps output locale from target.

- [ ] **Step 2: Verify RED**

Run: `PYTHONPATH=services/ai python -m unittest services.ai.tests.test_extension_exe_contract -v`
Expected: FAIL on hardcoded destination.

- [ ] **Step 3: Implement destination propagation**

Add destination selector; enforce same compatibility rules as Desktop; persist it; propagate to background/offscreen; include it in capture state; make all WebSocket messages use session destination.

- [ ] **Step 4: Implement destination-aware TTS**

Read `targetLanguage`/capture state and set Chrome TTS `lang` to `es-ES`, `en-US` or `zh-CN`; prefer voices matching target prefix.

- [ ] **Step 5: Verify GREEN**

Run: `PYTHONPATH=services/ai python -m unittest services.ai.tests.test_extension_exe_contract -v`
Expected: PASS.

---

### Task 6: Release gates and promotion candidate

**Files:**
- Modify: `.github/workflows/enginehub-pruebas.yml` only if the new tests are not already covered by discovery.
- Modify: `docs/release/RELEASE_NOTES_2.1.0.md` to describe the bidirectional Quality lane accurately.

**Interfaces:** none; this task certifies the integrated SHA.

- [ ] **Step 1: Run full local/static suites available in CI**

Run Python unit discovery, frontend typecheck/tests/build, Rust format/tests/clippy where available.

- [ ] **Step 2: Push one integrated candidate to `pruebas`**

Expected: Engine Hub fast preflight SUCCESS.

- [ ] **Step 3: Open PR `pruebas → main` only after preflight**

The PR body must state that ES→EN/ES→ZH are Quality M2M100 lanes, not 2 GB Lite-certified lanes.

- [ ] **Step 4: Require full CI on the PR SHA**

Do not merge if Windows runtime/NSIS/extension/gates fail. Merge only exact green SHA.
