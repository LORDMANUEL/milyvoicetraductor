# MilyVoice 3 TTS 1.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver MilyVoice TTS 1.0.0 as an optional, bounded, local Chromium/Windows speech component with real ducking, anti-feedback preservation, subtitle fallback, contract `tts/v1`, and Linux/Windows gates.

**Architecture:** Keep synthesis in the existing Chromium extension where `chrome.tts` and installed OS voices already work. Add a pure JavaScript controller that owns queue freshness/health, retain `apps/extension/tts.js` as the browser adapter, make offscreen audio own ducking, and expose a portable `tts/v1` contract so future Desktop-native synthesis can implement the same boundary.

**Tech Stack:** Manifest V3 ES modules, JavaScript, Node 22 built-in test runner, Chromium `chrome.tts`, Web Audio API, Python Contracts Kernel scripts, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-24-milyvoice-3-tts-1.0-design.md`

## Global Constraints

- Base branch is `v3/integration`; `main` 2.1.x is not modified.
- Product-wide target remains <= 2 GiB RAM and <= 512 MiB VRAM on the low-end profile.
- F9 adds no model weights, native TTS runtime, GPU dependency, remote service, or required network call.
- `maxPending = 3`; `maxAgeMs = 4000`.
- TTS is optional; subtitles remain the required output path.
- No gender/age/identity inference from speaker audio.
- Every terminal TTS path restores ducking.
- TTS failure/stop must not stop capture, ASR, MT, Realtime, Engine Host, or the WebSocket session.
- Final F9 lifecycle is `candidate`; real Windows/Chromium audible validation is required for `certified`.

---

### Task 1: Pure bounded TTS controller

**Files:**
- Create: `apps/extension/tts/controller.js`
- Create: `apps/extension/tts/controller.test.mjs`

**Interfaces:**
- Produces: `TtsQueueController` with constructor `{maxPending = 3, maxAgeMs = 4000, now = () => Date.now()}`.
- Produces: `enqueue(job)`, `takeNext()`, `finish(reason)`, `reset(reason)`, `snapshot()`.
- Job shape: `{requestId, utteranceId, text, speakerId, targetLanguage, voiceName, duckingEnabled, duckingLevel, createdAt, lifecycle}`.

- [ ] **Step 1: Write failing Node tests** covering constructor validation, one active + three pending maximum, oldest-pending overflow drop, stale skip, finish -> next, reset, and health/degraded counters.
- [ ] **Step 2: Run RED** with `node --experimental-default-type=module --test apps/extension/tts/controller.test.mjs`; expected failure because `controller.js` does not exist.
- [ ] **Step 3: Implement minimal controller** using only arrays and scalar state; never persist text.
- [ ] **Step 4: Run GREEN** with the same command on Linux-compatible Node behavior.
- [ ] **Step 5: Commit** `feat(v3-tts): add bounded TTS queue controller`.

### Task 2: Chromium adapter and voice policy

**Files:**
- Modify: `apps/extension/tts.js`
- Create: `apps/extension/tts/adapter.test.mjs`
- Create: `apps/extension/tts/COMPONENT.json`

**Interfaces:**
- `speakTranslation(payload, lifecycle = {}) -> Promise<boolean>` remains the compatibility API used by `background.js`.
- Adapter resolves speaker-specific voice before global voice, then OS default.
- Adapter calls `chrome.tts.speak(..., {enqueue:false})` only when the controller grants an active job.

- [ ] **Step 1: Write failing adapter tests** with a mocked `globalThis.chrome` for disabled mode, empty text, speaker/global/default voice order, language defaults, `enqueue:false`, runtime error fallback, cancellation and automatic next-job start.
- [ ] **Step 2: Run RED** and confirm current adapter fails bounded-queue/enqueue-false cases.
- [ ] **Step 3: Refactor `tts.js`** to use `TtsQueueController`; keep current public function and lifecycle callbacks.
- [ ] **Step 4: Add component metadata** `{id:"tts", version:"1.0.0", contract:"tts/v1", stage:"development"}`.
- [ ] **Step 5: Run controller + adapter GREEN**.
- [ ] **Step 6: Commit** `feat(v3-tts): integrate Chromium TTS adapter`.

### Task 3: Real ducking and anti-feedback lifecycle

**Files:**
- Modify: `apps/extension/background.js`
- Modify: `apps/extension/offscreen.js`
- Modify: `scripts/test_extension.py`
- Create: `apps/extension/tts/ducking.test.mjs`

**Interfaces:**
- `TTS_STARTED` carries `text`, `speakerId`, `duckingEnabled`, `duckingLevel`.
- Offscreen stores the tab reinjection gain node and applies `0.05..1.0` only while TTS is active.
- `TTS_FINISHED`/cleanup restores `1.0`.

- [ ] **Step 1: Write failing static/runtime tests** proving current offscreen code does not retain/apply ducking.
- [ ] **Step 2: Run RED**.
- [ ] **Step 3: Modify background lifecycle forwarding** to include ducking settings from the actual TTS start callback.
- [ ] **Step 4: Add offscreen ducking actuator** with a module-level playback gain reference, clamp helper, start/finish/reset paths, and no capture stop.
- [ ] **Step 5: Extend extension guard** to require bounded controller, `enqueue:false`, ducking application/restoration, and continued `tts.started`/`tts.finished` anti-feedback signaling.
- [ ] **Step 6: Run GREEN**: Node TTS tests plus `python scripts/test_extension.py`.
- [ ] **Step 7: Commit** `feat(v3-tts): apply ducking and preserve anti-feedback`.

### Task 4: Publish `tts/v1`

**Files:**
- Create: `contracts/tts/v1/contract.json`
- Create: `contracts/tts/v1/compatibility.lock.json`
- Create: `contracts/tts/v1/examples/request.json`
- Create: `contracts/tts/v1/examples/lifecycle-event.json`
- Create: `contracts/tts/v1/examples/snapshot.json`
- Modify: `contracts/index.json`

**Interfaces:**
- Messages: `TtsRequest`, `TtsLifecycleEvent`, `TtsSnapshot`.
- Enums: `TtsState`, `TtsReason`, `TtsHealth`.

- [ ] **Step 1: Register `tts/v1` first without descriptor** to produce a Contracts Kernel RED while self-test remains green.
- [ ] **Step 2: Run RED** `python scripts/test_v3_contracts.py`; expected missing `contracts/tts/v1/contract.json`.
- [ ] **Step 3: Add descriptor/examples/lock** using only scalar, enum and array field types supported by Contracts Kernel v1.
- [ ] **Step 4: Run GREEN** and verify registry count becomes nine contracts.
- [ ] **Step 5: Commit** `feat(v3-tts): publish tts v1 contract`.

### Task 5: Candidate lifecycle and product composition

**Files:**
- Modify: `apps/extension/tts/COMPONENT.json`
- Modify: `manifests/milyvoice-3.components.json`
- Modify: `scripts/test_v3_component_manifest.py` only if the existing generic validator cannot express the new expected composition.

**Interfaces:**
- Product version advances to `3.0.0-alpha.4-dev.4`.
- TTS manifest entry: `{id:"tts", version:"1.0.0", contract:"tts/v1", stage:"candidate", required:false}`.

- [ ] **Step 1: Add lifecycle/composition tests expecting candidate/dev.4 before changing metadata**.
- [ ] **Step 2: Run RED** and prove the only mismatch is development/old composition.
- [ ] **Step 3: Promote `COMPONENT.json` to candidate and add TTS to product manifest**.
- [ ] **Step 4: Run GREEN** for Contracts Kernel and component manifest.
- [ ] **Step 5: Commit** `feat(v3-tts): compose TTS candidate`.

### Task 6: Dedicated CI and cross-gates

**Files:**
- Create: `.github/workflows/v3-tts.yml`

**Interfaces:**
- Linux and Windows jobs use Node 22.
- TTS contract/composition job uses Python Contracts Kernel scripts.

- [ ] **Step 1: Add workflow** with path filters for `apps/extension/tts.js`, `apps/extension/tts/**`, `apps/extension/background.js`, `apps/extension/offscreen.js`, `scripts/test_extension.py`, `contracts/tts/**`, registry, composition and TTS docs.
- [ ] **Step 2: Linux gate** runs all TTS Node tests and `python scripts/test_extension.py`.
- [ ] **Step 3: Windows gate** runs the same tests on `windows-latest`.
- [ ] **Step 4: Contract/composition gate** runs `scripts/test_v3_contracts.py` and `scripts/test_v3_component_manifest.py`.
- [ ] **Step 5: Open draft PR to `v3/integration` and freeze the head**.
- [ ] **Step 6: Require SUCCESS on V3 TTS plus Contracts Kernel, Supervisor, Audio, Realtime, Engine Host, ASR, Linguistic and MT for the exact head SHA.
- [ ] **Step 7: Review diff boundary**: no model pack, provider, ASR/MT implementation, Desktop, installer, global VERSION, or `main` changes.
- [ ] **Step 8: Mark ready and merge only if all exact-head gates are green.**

## Self-review

- Spec coverage: queue, voices, ducking, anti-feedback, failure isolation, resource limits, contract, lifecycle and cross-gates are mapped to tasks.
- Placeholder scan: no TBD/TODO/unspecified implementation steps remain.
- Type consistency: request/utterance IDs, queue limits, lifecycle states and component metadata are named consistently across tasks.
