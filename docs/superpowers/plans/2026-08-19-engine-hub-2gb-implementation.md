# MilyVoice Engine Hub 2.1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hardware-adaptive, multi-engine speech translation runtime that keeps the complete MilyVoice process below a 2 GiB hard memory budget, supports a 512 MiB VRAM-class machine, and prevents cumulative subtitle lag.

**Architecture:** Keep `v2.0.1` as the stable baseline. Development occurs on `pruebas` as `2.1.0-dev`. Add a provider registry and resource governor around the existing pipeline, introduce a real lightweight EN→ES pack (Whisper Tiny + OPUS-MT Tiny CT2 INT8), register Moonshine, sherpa-onnx, whisper.cpp and cloud adapters, and select only combinations that pass compatibility, memory and latency gates. Exactly one ASR model and one MT model may be resident at a time.

**Tech Stack:** Python 3.13, CTranslate2, Faster-Whisper, optional Moonshine Voice, sherpa-onnx, whisper.cpp sidecar, FastAPI/WebSocket, Rust/Tauri 2, Svelte/TypeScript.

**Spec:** `MASTER.md` plus the approved Engine Hub 2.1 design in the project conversation.

## Global Constraints

- MilyVoice process hard limit: `2 GiB` resident memory.
- Lite target: `<= 1.2 GiB` steady-state and `<= 1.5 GiB` peak.
- Rescue target: `<= 700 MiB` for subtitles-only operation.
- VRAM-class compatibility: `512 MiB`; MilyVoice allocatable VRAM ceiling defaults to `384 MiB`.
- CPU is always available and remains the mandatory fallback.
- At most one ASR model, one translation model and one tokenizer are resident.
- Final transcriptions/translations are never dropped.
- Stale partial translations are coalesced by utterance and never block a final result.
- External model packs may contain data/model files only; no arbitrary Python, executable, DLL or `trust_remote_code` payloads.
- `v2.0.1` and `main` are not modified until the new branch passes all gates.

---

### Task 1: Resource Governor and 2 GiB contracts

**Files:**
- Create: `services/ai/mily_ai/resource_governor.py`
- Create: `services/ai/tests/test_resource_governor.py`

**Interfaces:**
- Produces `ResourceLimits`, `RuntimeFootprint`, `ResourceDecision`, `ResourceGovernor`.
- `ResourceGovernor.evaluate(footprint) -> ResourceDecision` is consumed by model selection and runtime pressure control.

- [ ] Write failing tests for 2 GiB hard rejection, 384 MiB VRAM ceiling, integrated-GPU shared-memory accounting, Lite and Rescue modes.
- [ ] Run the focused test and confirm RED.
- [ ] Implement immutable limits and deterministic decisions.
- [ ] Run focused and complete Python test suites.

### Task 2: Engine Registry v2 and automatic selection

**Files:**
- Create: `services/ai/mily_ai/engine_registry.py`
- Create: `services/ai/mily_ai/engine-families.json`
- Create: `services/ai/tests/test_engine_registry.py`

**Interfaces:**
- Produces `EngineDescriptor`, `EngineCandidate`, `BenchmarkSample`, `EngineSelection`, `EngineRegistry`.
- `EngineRegistry.select(...)` filters unsupported language routes, unavailable runtimes, license restrictions and resource violations, then ranks valid candidates by measured RTF, P95 latency, memory and quality tier.

- [ ] Write failing tests proving that a fast candidate inside budget beats a quality candidate that exceeds 2 GiB, CPU fallback remains selectable, and cloud engines require explicit consent.
- [ ] Run RED.
- [ ] Implement schema validation and deterministic scoring.
- [ ] Run focused and complete Python tests.

### Task 3: Coalescing realtime queue

**Files:**
- Modify: `services/ai/mily_ai/pipeline.py`
- Replace: `services/ai/mily_ai/queueing.py`
- Modify: `services/ai/mily_ai/server.py`
- Create: `services/ai/tests/test_coalescing_queue.py`

**Interfaces:**
- Produces `CoalescingTranslationQueue` with `put`, `get`, `task_done`, `empty`, `qsize`, `close`.
- Partials are keyed by utterance; a newer partial replaces the older partial. Finals remove their partial and enter the priority lane.

- [ ] Add `utterance_id` and creation timestamp to translation requests.
- [ ] Write tests that fail under the current FIFO queue: stale partial replacement, final priority and age-based eviction.
- [ ] Implement the queue and update server telemetry to report queue age.
- [ ] Verify no final is dropped and backlog does not grow in the stress test.

### Task 4: Provider Factory and lightweight translation provider

**Files:**
- Create: `services/ai/mily_ai/provider_factory.py`
- Modify: `services/ai/mily_ai/providers.py`
- Modify: `services/ai/mily_ai/pipeline.py`
- Create: `services/ai/tests/test_provider_factory.py`

**Interfaces:**
- `build_asr_provider(component, model_path, compute_profile, cpu_budget, word_timestamps)`.
- `build_translation_provider(component, model_path, compute_profile, cpu_budget)`.
- Add `CTranslate2MarianTranslator` for direct OPUS-MT/Marian pairs.
- Register adapters for `faster-whisper`, `moonshine`, `sherpa-onnx`, `whisper-cpp`, and `google-chirp`; optional adapters must fail with a stable public error when their runtime/configuration is unavailable.

- [ ] Write factory tests first.
- [ ] Implement Marian CT2 beam-1 decoding and unload support.
- [ ] Route the pipeline exclusively through the factory.
- [ ] Verify existing M2M100 tests remain green.

### Task 5: Model Pack schema v2 and Lite packs

**Files:**
- Modify: `services/ai/mily_ai/model-packs.json`
- Modify: `services/ai/mily_ai/models.py`
- Create: `services/ai/tests/test_model_pack_v2.py`

**Interfaces:**
- Pack metadata adds `tier`, `routes`, `ramMb`, `vramMb`, `engine`, `format`, `supportedBackends`, `bundled`, `externalAllowed`.
- Add `lite-en-es` using Faster-Whisper Tiny EN INT8 + OPUS-MT Tiny EN→ES CT2 INT8.
- Add catalog descriptors for Moonshine, sherpa-onnx, whisper.cpp and cloud profiles without falsely marking them installed.

- [ ] Write schema and security tests first.
- [ ] Generalize Transformers→CT2 conversion for Marian while retaining M2M100 tokenizer handling.
- [ ] Reject executable/script payloads during external pack import.
- [ ] Add install/activate/remove/import API methods.

### Task 6: Model Manager API and simple UI

**Files:**
- Modify: `services/ai/mily_ai/server.py`
- Modify: `apps/desktop/src/pages/Models.svelte`
- Modify: `apps/desktop/src/types.ts`
- Add or modify frontend tests under `apps/desktop/src/**/*.test.ts`.

**Interfaces:**
- `GET /v1/engines`, `POST /v1/models/select-auto`, `POST /v1/models/import`, `DELETE /v1/models/{id}/{version}`.
- UI actions: `Optimizar automáticamente`, `Descargar`, `Activar`, `Eliminar`, `Importar .mmpack`, `Agregar repositorio externo`.
- Show RAM, VRAM, engine, route, license and benchmark status.

- [ ] Add failing API/frontend tests.
- [ ] Implement authenticated API.
- [ ] Implement simplified UI without exposing ports/tokens.
- [ ] Run frontend typecheck/tests/build.

### Task 7: Runtime pressure states and benchmark gate

**Files:**
- Modify: `services/ai/mily_ai/telemetry.py`
- Modify: `services/ai/mily_ai/server.py`
- Create: `services/ai/mily_ai/engine_benchmark.py`
- Create: `services/ai/tests/test_runtime_pressure.py`
- Create: `services/ai/tests/test_engine_benchmark.py`

**Interfaces:**
- Pressure states: `healthy`, `pressure`, `catch_up`, `rescue`.
- `catch_up` disables partial MT, speaker work and optional TTS work.
- `rescue` selects a Lite pack and final-only subtitles.

- [ ] Test state transitions and recovery hysteresis.
- [ ] Add memory/queue-age metrics.
- [ ] Add a repeatable benchmark report with RTF/P50/P95/RAM/VRAM.
- [ ] Require no cumulative backlog over a ten-minute synthetic stream.

### Task 8: Installer and CI gates

**Files:**
- Modify: `services/ai/requirements.runtime.txt`
- Modify: `installer/windows/build-python-runtime.ps1`
- Modify: `.github/workflows/ci.yml`
- Add Windows scripts/tests for the 2 GiB and Lite-pack gates.

**Interfaces:**
- Runtime includes adapters but only loads the selected engine.
- CI validates static dependency policy, model catalog, Lite path, no executable external pack content, memory contracts and realtime backlog.

- [ ] Add failing release-policy checks.
- [ ] Update runtime build.
- [ ] Add MegaBench Lite alongside Quality MegaBench.
- [ ] Build/install/reinstall NSIS and upload the same-SHA artifacts.

### Task 9: Product documentation and versioning

**Files:**
- Modify: `MASTER.md`
- Modify: `CHANGELOG.md`
- Add: `docs/architecture/ENGINE_HUB_2_1.md`

- [ ] Document exact implemented engines versus optional adapters.
- [ ] Document the 2 GiB process contract and 4/8 GiB host recommendations.
- [ ] Keep public README/Pages on 2.0.1 until 2.1 passes all release gates.
