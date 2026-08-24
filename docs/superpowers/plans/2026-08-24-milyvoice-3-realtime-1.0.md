# MilyVoice 3 — Realtime 1.0 Implementation Plan

**Goal:** Build `realtime 1.0.0` as a stdlib-only timing/backpressure component that consumes Audio v1, eliminates progressive timestamp-derived drift, detects sequence/timestamp anomalies and bounds retained audio under downstream pressure.

**Spec:** `docs/superpowers/specs/2026-08-24-milyvoice-3-realtime-1.0-design.md`

## Constraints

- Do not modify `services/audio/**` during F5.
- Do not modify `crates/mily-compute/**`, Supervisor, legacy AI, Desktop, extension or installer.
- Production `mily_realtime` has no NumPy/PyAudio dependency and does not import `mily_audio`.
- Integration tests may import `mily_audio` through PYTHONPATH to prove the actual producer contract.
- Media position is derived from sample counts/rates, never processing delay.
- Queue memory is bounded by count and media duration.
- Global `VERSION` remains 2.1.0.

### Task 1 — Package/workflow and timeline RED

Create:
- `services/realtime/pyproject.toml`
- `services/realtime/COMPONENT.json` (`development`)
- `.github/workflows/v3-realtime.yml`
- `services/realtime/tests/test_timeline.py`

RED requirements:
- first chunk sequence 0 accepted;
- continuous chunks get exact sample-derived media offsets;
- capture jitter does not move media offsets;
- sequence gaps are accepted and reported explicitly;
- duplicate/out-of-order chunks are rejected;
- monotonic timestamp regression is rejected;
- explicit discontinuity starts a new epoch at sequence/media zero.

### Task 2 — Timeline GREEN

Create:
- `services/realtime/mily_realtime/__init__.py`
- `services/realtime/mily_realtime/timeline.py`

API:
- `RealtimeTimeline`
- `RealtimeFrame`
- `TimelineError` with stable code
- immutable frame descriptor fields plus payload reference
- `TimelineSnapshot`

No Audio import in production.

### Task 3 — Bounded queue RED/GREEN

Create:
- `services/realtime/tests/test_queue.py`
- `services/realtime/mily_realtime/queue.py`

API:
- `BackpressurePolicy::{REJECT_NEW,DROP_OLDEST}`
- `BoundedRealtimeQueue`
- `QueueOfferResult`
- `QueueSnapshot`

Tests:
- max chunk bound;
- max media-duration bound;
- rejectNew leaves queue unchanged;
- dropOldest evicts only what is required;
- too-large single frame rejected;
- FIFO pop order;
- counters exact.

### Task 4 — Real Audio producer consumer test

Create:
- `services/realtime/tests/test_audio_contract_consumer.py`

Workflow installs only pinned NumPy for tests and sets both package roots on PYTHONPATH. The test constructs `mily_audio.AudioIngress` from F4, produces real `AudioChunk` objects and feeds them into `RealtimeTimeline` without a production dependency on Audio.

Gate proves:
- Audio source enum/string is preserved;
- sequence/timestamp/sample metadata are consumed;
- payload object is retained by reference (no copy);
- 16 kHz mono 100 ms Audio chunk maps to exactly 100,000,000 ns.

### Task 5 — Long-run drift/backpressure gate

Create:
- `services/realtime/tests/test_long_run.py`

Simulate 36,000 x 100 ms chunks = 60 minutes with deterministic capture jitter and periodic CPU-like stalls. Require:
- media cursor exactly 3,600,000,000,000 ns after final chunk;
- max jitter recorded but not accumulated into media cursor;
- no sequence errors for continuous input;
- queue remains within configured count/duration after sustained pressure.

### Task 6 — `realtime/v1`

Modify/create:
- `contracts/index.json`
- `contracts/realtime/v1/contract.json`
- `contracts/realtime/v1/compatibility.lock.json`
- fixtures under `contracts/realtime/v1/examples/`

Contract metadata only; payload remains out-of-band.

Enums:
- `BackpressurePolicy`: rejectNew, dropOldest
- `RealtimeAnomaly`: gap, outOfOrder, timestampRegression

Messages:
- `RealtimeFrameDescriptor`
- `RealtimeTimelineSnapshot`
- `RealtimeQueueSnapshot`

### Task 7 — Component candidate + development composition

Create test-first metadata assertion and then promote:
- `services/realtime/COMPONENT.json`: development -> candidate.

Modify test-first:
- `scripts/test_v3_component_manifest.py`
- `manifests/milyvoice-3.components.json`

Composition becomes `3.0.0-alpha.3-dev.1`:
- Supervisor 1.0.0 candidate
- Compute 2.0.0 certified
- Audio 1.0.0 candidate
- Realtime 1.0.0 candidate

### Task 8 — Final boundary/certification

Allowed paths:
```text
.github/workflows/v3-realtime.yml
services/realtime/**
contracts/index.json
contracts/realtime/**
manifests/milyvoice-3.components.json
scripts/test_v3_component_manifest.py
docs/superpowers/specs/2026-08-24-milyvoice-3-realtime-1.0-design.md
docs/superpowers/plans/2026-08-24-milyvoice-3-realtime-1.0.md
```

Require exact-head:
- Realtime Linux tests PASS;
- Realtime Windows tests PASS;
- 60-minute stress PASS;
- Audio producer consumer PASS;
- Contracts Kernel PASS;
- composition PASS;
- Supervisor/Compute/Audio cross-gates PASS if triggered.

Merge only to `v3/integration`. Realtime ends `candidate`; F6 consumes it before any certification/freeze decision.
