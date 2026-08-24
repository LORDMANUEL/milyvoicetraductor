# MilyVoice 3 — MilyCompute 2.0 Implementation Plan

**Goal:** Certify the existing `mily-compute` foundation as independently versioned component `compute 2.0.0`, add an explicit status/compatibility surface and publish `compute/v1` without rewriting working benchmark/cache/memory/runtime code.

**Spec:** `docs/superpowers/specs/2026-08-23-milyvoice-3-compute-2.0-design.md`

## Constraints

- Keep `mily-system` unchanged; it owns hardware discovery.
- Keep root product `VERSION` unchanged.
- Keep root Cargo package/workspace versioning unchanged during F3.
- Do not mark optional runtimes ready without an adapter.
- Do not add fake ROCm/WindowsML adapter readiness.
- Existing benchmark/cache/memory/runtime behavior is retained unless a test proves a defect.
- F3 may modify only Compute-owned source/tests, Compute contract/metadata/composition, its workflow, and F3 docs.

### Task 1 — Explicit backend status RED/GREEN

Files:
- Create `crates/mily-compute/tests/capability_status.rs`
- Modify `crates/mily-compute/src/lib.rs`
- Modify `crates/mily-compute/src/registry.rs`

RED tests:
- CPU status is `Ready`.
- detected DirectML with no adapter is `DetectedNotReady`.
- absent Vulkan is `Unavailable`.
- after adapter validation DirectML is `Ready`.
- capability snapshot contains every `ComputeBackend` exactly once in deterministic order.

GREEN API:
- `BackendStatus::{Ready, DetectedNotReady, Unavailable}`.
- `BackendCapability::status()`.
- `BackendRegistry::status(backend)`.
- `BackendRegistry::capability_snapshot()` returning public `BackendCapabilityState` values.

### Task 2 — Model compatibility filter RED/GREEN

Files:
- Create `crates/mily-compute/tests/compatibility_filter.rs`
- Modify `crates/mily-compute/src/lib.rs` or focused new `compatibility.rs` module.

RED tests:
- only supported + ready backends are returned;
- detected-not-ready backend is excluded;
- unsupported ready backend is excluded;
- profile too large for memory returns empty;
- CPU remains eligible when explicitly supported and memory fits;
- deterministic backend order is preserved.

GREEN API:
- `ModelComputeProfile { supported_backends, resident_memory_mb }`.
- `compatible_backends(registry, profile, budget)`.

### Task 3 — Independent component metadata

Files:
- Create `crates/mily-compute/COMPONENT.json`
- Create `crates/mily-compute/tests/component_metadata.rs`

Metadata:
```json
{
  "id": "compute",
  "package": "mily-compute",
  "version": "2.0.0",
  "contract": "compute/v1",
  "stage": "candidate"
}
```

Test uses `include_str!` + existing `serde_json` to assert exact fields and strict 2.0.0/compute-v1 identity.

### Task 4 — Publish `compute/v1`

Files:
- Modify `contracts/index.json`
- Create `contracts/compute/v1/contract.json`
- Create `contracts/compute/v1/compatibility.lock.json`
- Create fixtures under `contracts/compute/v1/examples/`

Contract mirrors the certified public DTO surface only. Numeric metrics use Contracts Kernel `number`/`integer` types.

Required fixtures:
- capability snapshot entry;
- benchmark observation;
- memory budget;
- model compute profile.

Run `python scripts/test_v3_contracts.py` and require both supervisor/v1 and compute/v1 PASS.

### Task 5 — Add Compute to 3.x composition

Files:
- Modify `manifests/milyvoice-3.components.json`
- Modify `scripts/test_v3_component_manifest.py` only to assert the new expected Compute descriptor while preserving Supervisor assertion.

Composition remains product `3.0.0-alpha.1` and adds:
```json
{"id":"compute","version":"2.0.0","contract":"compute/v1","stage":"candidate","required":true}
```

### Task 6 — Isolated certification workflow

Files:
- Create `.github/workflows/v3-compute.yml`

Jobs:
1. Linux Compute gate: fmt, `cargo test -p mily-compute --locked`, Clippy.
2. Windows Compute gate: `cargo test -p mily-compute --locked` to exercise Windows runtime-candidate paths.
3. Contract/composition gate: Contracts Kernel + component manifest.

The root CI may also run because existing Compute source changes; if it does, it must remain green before integration.

### Task 7 — Boundary and promotion

Allowed F3 paths:
```text
.github/workflows/v3-compute.yml
crates/mily-compute/**
contracts/index.json
contracts/compute/**
manifests/milyvoice-3.components.json
scripts/test_v3_component_manifest.py
docs/superpowers/specs/2026-08-23-milyvoice-3-compute-2.0-design.md
docs/superpowers/plans/2026-08-23-milyvoice-3-compute-2.0.md
```

- Confirm `mily-system`, Supervisor, AI, Desktop, extension and installer unchanged.
- Require exact-head Linux + Windows + contract gates green.
- Keep lifecycle `candidate` until consumer contract exercise. If module certification evidence is complete, record that state in PR/report; `frozen` waits for a consumer integration phase.
- Merge only to `v3/integration`.
