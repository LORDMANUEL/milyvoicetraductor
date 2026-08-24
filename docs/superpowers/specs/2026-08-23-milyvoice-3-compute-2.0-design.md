# MilyVoice 3 — MilyCompute 2.0 Certification Design

## Purpose

F3 certifies the existing `mily-compute` foundation instead of rewriting it. The module already implements conservative runtime discovery, backend readiness registry, real-measurement scoring, memory budgets and hardware/model-scoped selection cache. F3 adds the missing public state/compatibility boundary, versioned `compute/v1` contract, component metadata and an isolated certification gate.

## Existing behavior retained

The following behavior is already implemented and remains authoritative unless a failing test proves a defect:

- CPU exists as safe fallback and is ready by default.
- Runtime detection does not imply adapter readiness.
- CUDA/DirectML/OpenVINO/Vulkan discovery is loader-based and conservative.
- Windows ML requires explicit catalog evidence through the probe abstraction.
- benchmark candidates require both runtime detected and adapter ready.
- benchmark summary uses clean samples, P95 latency/RTF and peak memory.
- selection ranks RTF first, latency second and memory third.
- failed/non-finite observations are not selected.
- memory budgeting reserves system/iGPU memory and disables heavy parallel stages on constrained machines.
- selection cache is keyed by hardware fingerprint + model pack + model version and is written through a temporary file.

## System/Compute boundary

`mily-system` owns physical hardware discovery: OS, architecture, CPU topology/features, RAM and GPU inventory.

`mily-compute` owns execution decisions: runtime availability, adapter readiness, compatibility filtering, benchmark scoring, memory budget and cached selection.

F3 does not duplicate `mily-system` hardware probing.

## Component versioning

MilyVoice 3 component version: **`compute 2.0.0`**.

The existing Rust package remains inside the legacy root workspace and therefore still inherits the 2.1.x package version during migration. F3 records the independent 3.x component version in `crates/mily-compute/COMPONENT.json`, the 3.x composition manifest and `compute/v1` contract. This avoids changing root `Cargo.lock`/all workspace package metadata merely to certify one module.

The component manifest is authoritative for MilyVoice 3 composition.

## Missing capability 1 — explicit backend status

The existing booleans are normalized into:

- `ready`: runtime detected + adapter validated;
- `detectedNotReady`: runtime detected but adapter not validated;
- `unavailable`: runtime not detected / no registry entry.

`BackendRegistry::status(backend)` must return `unavailable` for an absent optional backend rather than requiring consumers to interpret `Option<BackendCapability>`.

A deterministic `capability_snapshot()` covers all known backend enum variants and keeps CPU first. This gives Desktop/Engine Host a stable diagnostics surface without exposing registry internals.

## Missing capability 2 — compatibility filter

A model/profile declares:

- supported backend list;
- estimated resident model memory in MiB.

`compatible_backends(registry, profile, budget)` returns only backends that:

1. are explicitly supported by the profile;
2. are `ready` in the registry;
3. fit `MemoryBudget.max_model_resident_mb`.

If the model does not fit memory, the result is empty. CPU is a safe execution fallback only when the model itself supports CPU and fits memory; choosing a smaller model belongs to Model Router/Model Manager, not Compute.

The returned backend list follows deterministic registry order and is then benchmarked by the existing measurement path.

## Public contract `compute/v1`

The external language-neutral contract includes:

Enums:
- `ComputeBackend`: cpu, cuda, directMl, windowsMl, openVino, vulkan.
- `BackendStatus`: ready, detectedNotReady, unavailable.
- `MemoryTier`: constrained, standard, spacious.

Messages:
- `BackendCapabilityState`: backend, status, evidence[] (encoded as an array of message wrappers is avoided; v1 exposes status snapshot entries with optional evidence text only where needed).
- `BackendObservation`: backend, available, successful, latencyMs, rtf, memoryMb.
- `MemoryBudget`: tier, reserveSystemMb, reserveSharedGpuMb, maxModelResidentMb, cacheLimitMb, allowParallelHeavyStages.
- `ModelComputeProfile`: supportedBackends plus residentMemoryMb.

Because Contracts Kernel v1 currently models arrays of messages rather than primitive arrays, the contract uses repeated `SupportedBackend` message entries for supported backends and repeated `EvidenceItem` entries for evidence.

## Certification level

F3 initially sets `compute 2.0.0` and `compute/v1` to `candidate` while tests run on Linux and Windows. It may be promoted to `certified` in the same F3 PR only after:

- existing and new Rust tests pass;
- Clippy `-D warnings` passes;
- contract compatibility/fixtures pass;
- Linux and Windows module jobs pass;
- component metadata/composition consistency passes.

`frozen` is reserved until the next consuming module (Audio/Engine Host) exercises `compute/v1`; certification alone is not enough to claim consumer compatibility.

## Non-goals

- implementing CUDA/DirectML/OpenVINO/Vulkan inference adapters;
- marking a backend ready just because a runtime exists;
- implementing Windows ML catalog discovery beyond the existing probe boundary;
- adding ROCm/HIP before a real adapter/runtime integration exists;
- changing model weights;
- changing `mily-system`;
- changing global product `VERSION`;
- changing Desktop/extension/installer behavior.
