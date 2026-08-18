# Hardware-first Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exprimir el hardware existente y reducir latencia antes de entrenar o activar los cuatro modelos MilyVoice propios.

**Architecture:** Rust será la fuente de verdad para topología/hardware y pasará un contrato de capacidad al sidecar Python. El motor actual seguirá usando Faster-Whisper + CTranslate2/M2M100; primero se corrige reparto de CPU, detección de capacidades, selección de backend y observabilidad. Los modelos `milyvoice-4mt` permanecen `enabled=false` hasta la fase final.

**Tech Stack:** Rust 2024, sysinfo, Tauri 2, Python 3.13, faster-whisper, CTranslate2, Svelte/TypeScript.

**Spec:** `docs/superpowers/specs/2026-08-18-milyvoice-1.0.5-master-spec.md`

## Global Constraints

- `main` permanece estable; todos los cambios van a `pruebas`.
- No activar ni entrenar los cuatro modelos MilyVoice propios en esta fase.
- CPU sin GPU es primera clase; Intel Core i3 4th gen / Haswell 2C/4T es referencia mínima.
- El runtime final no debe mostrar `cmd.exe`, PowerShell ni consola.
- No se selecciona una GPU solo por existir: la selección final debe depender de capacidad/benchmark.
- Mantener privacidad local, logs saneados y cero secretos en repositorio.
- TDD: test rojo -> implementación mínima -> test verde -> commit.

---

### Task 1: CPU topology real y contrato Rust -> Python

**Files:**
- Modify: `crates/mily-system/src/lib.rs`
- Modify: `crates/mily-engine/Cargo.toml`
- Modify: `crates/mily-engine/src/lib.rs`
- Modify: `services/ai/mily_ai/cpu_budget.py`
- Modify: `services/ai/tests/test_cpu_budget.py`

**Interfaces:**
- Produces Rust env contract: `MILY_PHYSICAL_CPUS`, `MILY_LOGICAL_CPUS`, `MILY_CPU_AVX2`, `MILY_CPU_FMA`.
- Python consumes `MILY_PHYSICAL_CPUS` before using any fallback heuristic.

- [ ] Add failing tests for 2C/4T balanced behavior and environment precedence.
- [ ] Expose physical cores and CPU feature flags in `SystemSnapshot`.
- [ ] Pass hardware env vars when launching the AI engine.
- [ ] Make 2-core balanced use both cores for ASR without parallel oversubscription.
- [ ] Run Python tests and Rust workspace tests/Clippy in CI.

### Task 2: MilyCompute capability map and backend scoring

**Files:**
- Create: `crates/mily-compute/Cargo.toml`
- Create: `crates/mily-compute/src/lib.rs`
- Modify: `Cargo.toml`
- Modify: `apps/desktop/src-tauri/Cargo.toml`

**Interfaces:**
- `ComputeBackend`: `Cpu | Cuda | DirectMl | OpenVino | Vulkan`.
- `BackendObservation { backend, available, latency_ms, rtf, memory_mb }`.
- `select_best_backend(&[BackendObservation]) -> ComputeBackend` only selects successful measured candidates.

- [ ] Write failing tests for CPU fallback and benchmark winner selection.
- [ ] Implement capability structs without heavy GPU runtime dependencies.
- [ ] Implement deterministic backend scoring from measured latency/RTF.
- [ ] Keep CPU as mandatory fallback.
- [ ] Run Rust tests/Clippy Windows + Linux.

### Task 3: Hardware Advisor exposed to Desktop

**Files:**
- Modify: `apps/desktop/src-tauri/src/commands/mod.rs`
- Modify: `apps/desktop/src-tauri/src/lib.rs`
- Modify: `apps/desktop/src/types.ts`
- Modify: `apps/desktop/src/pages/Models.svelte`

**Interfaces:**
- New command returns CPU topology/features plus available backend hints and recommended compute profile.

- [ ] Add frontend contract tests.
- [ ] Expose advisor command via Tauri.
- [ ] Show `Recomendado para este equipo` without enabling unavailable model packs.
- [ ] Preserve current Model Manager install/verify/rollback behavior.

### Task 4: Runtime tuning for current models

**Files:**
- Modify: `services/ai/mily_ai/providers.py`
- Modify: `services/ai/mily_ai/pipeline.py`
- Modify: `services/ai/mily_ai/telemetry.py`
- Tests: existing realtime optimization suite plus new targeted tests.

**Interfaces:**
- Current Whisper/M2M100 pack remains default.
- Warm-up happens once per active direction.
- Pressure controller can reduce partial work before final work.

- [ ] Verify beam=1, bounded decoding, one-time warm-up and LRU translation cache.
- [ ] Add 2-core serial reuse profile; >=3-core parallel profile.
- [ ] Add telemetry fields for selected threads/profile/backend.
- [ ] Reject unbounded queue growth under synthetic pressure tests.

### Task 5: Non-CUDA GPU adapter foundation

**Files:**
- Extend `crates/mily-compute`.
- Add optional runtime probes/config metadata only; no kernel driver.

**Interfaces:**
- Detect capability for DirectML/Windows ML, OpenVINO and Vulkan as candidates.
- Actual model backend is only marked usable after a real inference adapter/benchmark exists.

- [ ] Detect backend availability without claiming model compatibility.
- [ ] Keep CUDA as one candidate, not the architecture.
- [ ] Do not route current CTranslate2 weights to DirectML/OpenVINO/Vulkan until an adapter exists.
- [ ] Persist local capability report for diagnostics.

### Task 6: Release gates before model work

- [ ] Full Python tests.
- [ ] Frontend tests/build.
- [ ] `cargo fmt --check`.
- [ ] `cargo test --workspace`.
- [ ] `cargo clippy --workspace --all-targets -- -D warnings` Linux + Windows.
- [ ] Windows Release GUI / no-console check.
- [ ] NSIS install test.
- [ ] Current real model pack smoke test.
- [ ] Only after these gates: resume the 4MT fine-tuning plan.
