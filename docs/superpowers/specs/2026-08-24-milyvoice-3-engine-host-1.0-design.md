# MilyVoice 3 — Engine Host 1.0 Component Design

## Purpose

F6 introduces `engine-host 1.0.0`: one lightweight runtime boundary that owns adapter discovery, load/unload, invocation and health. It does **not** decide which model/engine is best; Compute/Engine Registry already own compatibility and evidence-based selection. It also does not implement Whisper/Moonshine/Sherpa/MT/TTS yet; those adapters arrive in later component phases.

The host exists so Desktop/Supervisor never depend on provider internals and so an adapter exception is contained inside one service boundary.

## Architecture

```text
Realtime -> EngineHost -> Adapter protocol -> future ASR/MT/TTS adapters
             |
             +-> health/failure state
             +-> bounded loaded-adapter capacity
```

Production core is Python 3.13 stdlib-only. Real inference dependencies remain adapter-owned and optional.

## Adapter protocol

Each registered adapter has immutable metadata:
- id;
- kind (`asr`, `mt`, `tts`, `external`);
- title;
- semantic version;
- contract major it implements.

A factory creates an adapter object supporting:
- `load(config)`;
- `unload()`;
- `invoke(request)`;
- optional `health()`.

The host catches exceptions from factory/load/unload/invoke/health and converts them to stable `EngineHostError` codes. An exception from adapter A must not mutate or prevent invocation of adapter B.

## Lifecycle/status

Adapter runtime status:
- `registered`: descriptor exists, instance not loaded;
- `loading`: temporary internal transition;
- `healthy`: loaded and callable;
- `degraded`: loaded but health probe failed/degraded;
- `unhealthy`: load/invoke/unload failure requires explicit recovery;
- `unloaded`: previously loaded and successfully released.

Host health is derived from adapter states and capacity, not from engine quality.

## Capacity and 2 GiB target

The host has `max_loaded_adapters` (positive integer). It never silently evicts a loaded adapter. Loading beyond capacity returns `HOST_CAPACITY` so the orchestrator can make an explicit unload/load decision. This prevents accidental accumulation of multiple heavy model runtimes.

F6 tests use a small default; later resource orchestration may derive the limit from Compute/memory budgets.

## Invocation

`EngineInvocation` contains:
- request id;
- route;
- optional frame object/payload reference;
- metadata mapping owned by the caller.

The host does not copy a Realtime frame payload. F6 integration tests pass a real `mily_realtime.RealtimeFrame` and verify identity is preserved into the fake adapter.

Results are adapter-defined Python objects inside the service. `engine/v1` only standardizes control/health metadata; ASR/MT result contracts are owned by their later components.

## Failure isolation

### Factory/load failure
- host returns `ADAPTER_LOAD_FAILED`;
- adapter is not counted as successfully loaded;
- failure count/last error are recorded;
- other adapters remain untouched.

### Invocation failure
- host catches the adapter exception;
- adapter becomes `unhealthy`;
- failure counter increments;
- host returns `ADAPTER_INVOKE_FAILED`;
- other adapters remain healthy and callable.

### Health probe failure
- adapter becomes `degraded`;
- host snapshot still succeeds.

### Unload failure
- host catches it and returns `ADAPTER_UNLOAD_FAILED`;
- runtime is marked `unhealthy` so the caller cannot assume memory was released.

## Recovery

An unhealthy adapter may be explicitly unloaded/reloaded. F6 does not implement automatic restarts or process supervision; Supervisor process-restart policy is a later release. The host itself is a separate component/process boundary from Desktop.

## Control plane

`mily_engine_host.control` provides a JSON-lines control handler for safe lifecycle/diagnostic operations:
- `ping`;
- `discover`;
- `snapshot`;
- `load`;
- `unload`.

Actual media payload/inference invocation stays out-of-band/in-process for F6 because serializing PCM into JSON would violate the low-copy design. Later transport can use shared memory/IPC without changing the adapter lifecycle contract.

## Realtime consumer evidence

F6 is the first downstream consumer of `realtime/v1`. Production Engine Host does not import Realtime; the integration test imports `mily_realtime`, creates a real frame, invokes a fake adapter through Engine Host, and verifies sequence/media metadata and payload identity.

## Contract `engine/v1`

Language-neutral metadata only:
- AdapterDescriptor;
- AdapterHealth;
- EngineHostSnapshot;
- EngineControlRequest;
- EngineControlResponse.

Enums:
- AdapterKind: asr, mt, tts, external;
- AdapterStatus: registered, loading, healthy, degraded, unhealthy, unloaded;
- ControlOperation: ping, discover, snapshot, load, unload.

No model weights, transcript payloads or PCM are serialized by `engine/v1`.

## Component/version

- component id: `engine-host`
- version: `1.0.0`
- contract: `engine/v1`
- stage: development -> candidate after F6 gates.

## Composition

F6 completes `3.0.0-alpha.3`:
- Supervisor 1.0.0 candidate
- Compute 2.0.0 certified
- Audio 1.0.0 candidate
- Realtime 1.0.0 candidate
- Engine Host 1.0.0 candidate

## Non-goals

- selecting engines/models;
- ASR/MT/TTS implementation;
- automatic adapter eviction;
- automatic process restart;
- serializing audio into JSON;
- modifying Realtime/Audio/Compute internals;
- modifying Desktop/extension/installer/global VERSION.
