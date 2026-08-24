# MilyVoice 3 — Engine Host 1.0 Implementation Plan

**Goal:** Build a stdlib-only `engine-host 1.0.0` that owns adapter lifecycle/health/failure containment and consumes Realtime by contract without embedding any concrete ASR/MT/TTS provider.

**Spec:** `docs/superpowers/specs/2026-08-24-milyvoice-3-engine-host-1.0-design.md`

## Constraints

- Do not modify Realtime, Audio, Compute, Supervisor or legacy AI provider implementations.
- Do not copy engine selection/scoring into Engine Host.
- Production Engine Host has no inference dependency.
- No silent adapter eviction.
- No PCM serialization through JSON control plane.
- Global VERSION remains 2.1.0.

### Task 1 — Package/workflow and lifecycle RED

Create:
- `services/engine_host/pyproject.toml`
- `services/engine_host/COMPONENT.json` stage development
- `.github/workflows/v3-engine-host.yml`
- `services/engine_host/tests/test_host_lifecycle.py`

RED requirements:
- unique adapter registration;
- deterministic descriptor order;
- load -> healthy;
- duplicate load is idempotent;
- unload -> unloaded;
- invoke requires loaded/healthy adapter;
- capacity refuses extra load without evicting another adapter.

### Task 2 — Lifecycle GREEN

Create:
- `services/engine_host/mily_engine_host/__init__.py`
- `services/engine_host/mily_engine_host/host.py`

API:
- `AdapterKind`
- `AdapterStatus`
- `AdapterDescriptor`
- `AdapterHealth`
- `EngineInvocation`
- `EngineHostSnapshot`
- `EngineHostError`
- `EngineHost`

Host keeps factory registry separate from loaded instances.

### Task 3 — Failure isolation RED/GREEN

Create:
- `services/engine_host/tests/test_failure_isolation.py`

Tests:
- factory/load exception -> ADAPTER_LOAD_FAILED and no capacity leak;
- invoke exception -> adapter unhealthy, failure count increments;
- failing adapter A does not mutate adapter B;
- health probe exception -> degraded snapshot, host snapshot still works;
- unload exception -> ADAPTER_UNLOAD_FAILED/unhealthy;
- explicit recovery path reloads a clean new instance.

### Task 4 — Realtime consumer contract

Create:
- `services/engine_host/tests/test_realtime_consumer.py`

PYTHONPATH includes Engine Host + Realtime. Create a real `RealtimeFrame` through `RealtimeTimeline`, invoke a fake adapter through Engine Host, and require:
- request/route preserved;
- frame metadata readable;
- frame payload is the exact same object;
- Realtime source/format enum sets in contracts remain compatible with Engine Host expectations where referenced.

### Task 5 — JSON-lines control plane

Create:
- `services/engine_host/mily_engine_host/control.py`
- `services/engine_host/mily_engine_host/__main__.py`
- `services/engine_host/tests/test_control.py`

Support line/request handling for:
- ping
- discover
- snapshot
- load
- unload

Unknown operations and malformed requests return structured error envelopes; the control loop stays alive after one bad request.

### Task 6 — `engine/v1`

Register test-first in `contracts/index.json`, then create:
- `contracts/engine/v1/contract.json`
- `contracts/engine/v1/compatibility.lock.json`
- fixtures.

Contract metadata only; no inference payload.

### Task 7 — candidate + alpha.3 composition

Test-first candidate metadata, then promote `services/engine_host/COMPONENT.json`.

Test-first composition expects final `3.0.0-alpha.3` with:
- supervisor 1.0.0 candidate
- compute 2.0.0 certified
- audio 1.0.0 candidate
- realtime 1.0.0 candidate
- engine-host 1.0.0 candidate

### Task 8 — final gates/boundary

Allowed paths:
```text
.github/workflows/v3-engine-host.yml
services/engine_host/**
contracts/index.json
contracts/engine/**
manifests/milyvoice-3.components.json
scripts/test_v3_component_manifest.py
docs/superpowers/specs/2026-08-24-milyvoice-3-engine-host-1.0-design.md
docs/superpowers/plans/2026-08-24-milyvoice-3-engine-host-1.0.md
```

Require exact-head:
- Engine Host Linux PASS;
- Engine Host Windows PASS;
- lifecycle/failure/recovery/control tests PASS;
- real Realtime consumer PASS;
- Contracts Kernel PASS;
- composition PASS;
- cross-gates PASS where triggered.

Merge only to `v3/integration`. F7 ASR is the first concrete adapter phase.
