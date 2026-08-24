# MilyVoice 3 — Audio 1.0 Implementation Plan

**Goal:** Extract the proven PCM/WASAPI behavior into standalone `services/audio`, add deterministic sequence/timing metadata, publish `audio/v1`, and keep legacy 2.1.x source untouched.

**Spec:** `docs/superpowers/specs/2026-08-23-milyvoice-3-audio-1.0-design.md`

## Constraints

- Do not edit `services/ai/mily_ai/audio.py` or `system_loopback.py` in F4.
- Do not edit `crates/mily-compute/**`; Compute 2.0.0 is certified.
- Use `numpy==2.5.2`, matching the validated private runtime.
- PyAudioWPatch remains lazy and optional for module CI.
- Audio payload stays binary/in-memory; JSON contract carries metadata only.
- Product `VERSION` remains 2.1.0.

### Task 1 — Package/PCM RED → GREEN

Create:
- `services/audio/pyproject.toml`
- `services/audio/COMPONENT.json`
- `services/audio/tests/test_pcm.py`
- `.github/workflows/v3-audio.yml`

RED: tests import `mily_audio.pcm` before source exists.

GREEN:
- copy the already proven PCM16 decode and `PcmChunkBuffer` behavior into `services/audio/mily_audio/pcm.py`;
- add a stress test with repeated 100 ms chunks proving retained samples stay bounded around the configured analysis window;
- reject odd/empty/oversized PCM16 input exactly as legacy behavior does.

### Task 2 — Sequenced ingress RED → GREEN

Create:
- `services/audio/tests/test_stream.py`
- `services/audio/mily_audio/stream.py`

API:
- `AudioSourceKind`
- `AudioChunk`
- `AudioIngress`

Tests:
- first sequence ID is 0;
- IDs increment exactly once per accepted chunk;
- monotonic timestamp comes from injected clock;
- source/sample rate/channel/sample count are preserved;
- non-finite sample rejected without consuming sequence ID;
- invalid channels/sample rate rejected;
- `reset(discontinuity=True)` restarts sequencing only when caller explicitly begins a new stream and marks first next chunk discontinuous.

### Task 3 — WASAPI extraction RED → GREEN

Create:
- `services/audio/tests/test_loopback.py`
- `services/audio/mily_audio/loopback.py`

Port proven behavior unchanged:
- default loopback open;
- stereo → mono;
- 48 kHz → 16 kHz resample;
- active-alternative probing after sustained silence;
- no failover to silent/broken alternative;
- close stream/backend safely.

CI uses fake devices; physical hardware gate is deferred.

### Task 4 — `audio/v1`

Modify:
- `contracts/index.json`

Create:
- `contracts/audio/v1/contract.json`
- `contracts/audio/v1/compatibility.lock.json`
- fixtures for chunk descriptor/device info.

Contract carries metadata only. `sampleFormat=float32`; payload remains out-of-band.

### Task 5 — Composition alpha.2

Modify:
- `manifests/milyvoice-3.components.json`
- `scripts/test_v3_component_manifest.py`

Change product composition to `3.0.0-alpha.2` and add:

```json
{"id":"audio","version":"1.0.0","contract":"audio/v1","stage":"candidate","required":true}
```

Supervisor remains candidate; Compute remains certified.

### Task 6 — Certification gate

Workflow jobs:
- Linux Audio: Python 3.13, `numpy==2.5.2`, compile, unit/stress tests.
- Windows Audio: same fake-backend suite to exercise Windows-compatible source code.
- Contract/composition: Contracts Kernel + V3 component manifest.

Boundary check: only Audio module, audio contract, composition, F4 workflow and F4 docs may change.

F4 merges only into `v3/integration`; never `main`.
