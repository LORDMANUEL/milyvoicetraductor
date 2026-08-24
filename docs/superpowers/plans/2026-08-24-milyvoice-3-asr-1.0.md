# MilyVoice 3 — ASR 1.0 Implementation Plan

**Goal:** Wrap the proven Whisper/Moonshine/Sherpa providers behind a lazy provider-neutral ASR component and publish `asr/v1` without modifying legacy inference internals.

**Spec:** `docs/superpowers/specs/2026-08-24-milyvoice-3-asr-1.0-design.md`

## Constraints

- Do not modify `services/ai/mily_ai/*provider*.py`, Realtime, Audio, Compute or Engine Host during F7.
- Production ASR package has no hard optional-inference import at package import time.
- Do not download model weights in unit CI.
- Do not reimplement provider selection/scoring/model management.
- PCM remains out-of-band.
- Global VERSION remains 2.1.0.

### Task 1 — Package/workflow and adapter RED

Create:
- `services/asr/pyproject.toml`
- `services/asr/COMPONENT.json` stage development
- `.github/workflows/v3-asr.yml`
- `services/asr/tests/test_adapter.py`

RED requirements:
- package import does not import `mily_ai`;
- load validates model/config/provider identity;
- fake builder receives exact component/modelPath/compute/cpu/word timestamp config;
- invoke validates 16k mono float32 window and required metadata;
- payload object passed by identity to provider;
- legacy segment/word seconds normalize to ms;
- text/language/metrics normalized;
- final uses `transcribe_final` when available;
- otherwise final uses `transcribe` + `finish_utterance`;
- unload clears provider.

### Task 2 — Concrete promoted adapters

Create:
- `services/asr/mily_asr/adapter.py`
- `services/asr/mily_asr/__init__.py`

Concrete classes:
- WhisperAsrAdapter -> `faster-whisper`
- MoonshineAsrAdapter -> `moonshine`
- SherpaZipformerAsrAdapter -> `sherpa-onnx`

### Task 3 — Engine Host integration

Create `services/asr/tests/test_engine_host_integration.py`.

Use real `mily_engine_host.EngineHost` and real `mily_realtime.RealtimeTimeline` with fake legacy providers. Require:
- all 3 concrete factories can register/load/invoke/unload;
- Realtime payload preserved by identity;
- Engine Host failure isolation works with ASR adapter exception;
- descriptors remain distinct/stable.

### Task 4 — Legacy factory compatibility

Create `services/asr/tests/test_legacy_factory_contract.py`.

Without loading weights:
- assert current `mily_ai.provider_factory.ASR_BUILDERS` contains `faster-whisper`, `moonshine`, `sherpa-onnx`;
- assert model-packs lite entries map to those provider ids and remain <= 1200 MiB total pack / provider estimates expected;
- patch/inject builder to prove default lazy loader calls current factory signature.

### Task 5 — `asr/v1`

Register test-first then create:
- `contracts/asr/v1/contract.json`
- `contracts/asr/v1/compatibility.lock.json`
- fixtures.

Messages:
- AsrRequestDescriptor
- AsrWord
- AsrSegment
- AsrMetrics
- AsrResult

### Task 6 — Candidate + alpha.4-dev.1 composition

Test-first metadata then promote ASR 1.0.0 to candidate.

Test-first composition then add ASR to `3.0.0-alpha.4-dev.1` while keeping previous component stages unchanged.

### Task 7 — Final gates/boundary

Allowed F7 paths:
```text
.github/workflows/v3-asr.yml
services/asr/**
contracts/index.json
contracts/asr/**
manifests/milyvoice-3.components.json
scripts/test_v3_component_manifest.py
docs/superpowers/specs/2026-08-24-milyvoice-3-asr-1.0-design.md
docs/superpowers/plans/2026-08-24-milyvoice-3-asr-1.0.md
```

Require exact-head:
- ASR Linux PASS;
- ASR Windows PASS;
- Engine Host/Realtime integration PASS;
- legacy factory/model-pack compatibility PASS;
- Contracts Kernel PASS;
- composition PASS;
- all previous cross-gates PASS where triggered.

Merge only to `v3/integration`. ASR ends candidate; real-weight promotion remains a later MegaBench/release gate.
