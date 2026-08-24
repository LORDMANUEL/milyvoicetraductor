# MilyVoice 3 — ASR 1.0 Component Design

## Purpose

F7 introduces `asr 1.0.0` as the provider-neutral speech-to-text boundary between Engine Host and the already proven local ASR implementations. It does not rewrite inference. It wraps the current Engine Hub provider factory lazily and normalizes requests/results into `asr/v1`.

Promoted local families for F7:
- Whisper Tiny through provider id `faster-whisper`;
- Moonshine Tiny Streaming through `moonshine`;
- Sherpa Zipformer 20M INT8 through `sherpa-onnx`.

`whisper-cpp`, Vosk and cloud providers remain available in legacy Engine Hub but are not promoted by this component until they pass the same adapter-level release gate.

## Ownership boundary

ASR owns:
- validation of the provider-neutral ASR request/window;
- lazy construction of an existing legacy ASR provider;
- delegation to `transcribe` / `transcribe_final` / `finish_utterance` where supported;
- normalization of segments/words/language/metrics;
- provider-independent health/unload semantics;
- `asr/v1`.

ASR does not own:
- Audio capture/resampling;
- Realtime sequence/timing;
- VAD/utterance segmentation;
- engine/model selection or benchmark scoring;
- model download/activation;
- translation or TTS.

## Input window

The caller owns utterance segmentation and passes a complete ASR window through `EngineInvocation.frame.payload`. For streaming providers such as Moonshine/Sherpa the caller may pass growing cumulative windows exactly as the current legacy pipeline does; the existing provider then sends only the delta internally.

The frame/window must declare:
- 16,000 Hz;
- mono;
- `float32`;
- positive sample count;
- sequence/media metadata.

`EngineInvocation.metadata` must contain:
- `utteranceId` non-empty string;
- `sourceLanguage` non-empty string (`auto`, `en`, `zh`, ...);
- optional `final` boolean, default false.

The adapter passes the payload object directly to the provider. It does not create another PCM copy.

## Legacy provider bridge

`LegacyAsrAdapter` is production stdlib-only until `load()` is called. The default loader imports:
- `mily_ai.provider_factory.build_asr_provider`;
- `mily_ai.cpu_budget.detect_cpu_budget`.

Required load configuration:
- `modelPath`;
- optional `component` mapping (provider-specific model metadata);
- optional `computeProfile`, default `auto`;
- optional `cpuProfile`, default `balanced`;
- optional `physicalCores`;
- optional `wordTimestamps`, default true.

The provider id is fixed by the concrete adapter class and conflicting `component.provider` is rejected.

Concrete adapters:
- `WhisperAsrAdapter` -> `faster-whisper`;
- `MoonshineAsrAdapter` -> `moonshine`;
- `SherpaZipformerAsrAdapter` -> `sherpa-onnx`.

Tests inject a fake builder/budget builder, so unit CI never downloads weights or imports optional inference runtimes.

## Result normalization

`AsrResult` includes:
- requestId;
- utteranceId;
- sequenceId;
- mediaStartNs/mediaEndNs;
- engineId;
- sourceLanguage;
- detectedLanguage;
- final;
- text;
- segments[];
- metrics.

Legacy segment timestamps are seconds and are normalized to milliseconds in `asr/v1`. Word timestamps are normalized the same way. Empty/whitespace-only segments are omitted. `text` is the space-joined normalized segment text.

Metrics:
- elapsedMs measured with a monotonic performance clock;
- audioDurationMs from the ASR window sample count at 16 kHz mono;
- rtf = elapsedMs / audioDurationMs.

## Finalization

When `final=true`:
1. if provider exposes `transcribe_final(samples, language)`, use it;
2. otherwise call normal `transcribe` then `finish_utterance()` if present.

This preserves Sherpa's explicit final tail and Moonshine's stream cleanup without duplicating provider internals.

## Failure behavior

Adapter validation/config/provider exceptions bubble as adapter exceptions to Engine Host. Engine Host already converts them into stable lifecycle error envelopes and marks the adapter unhealthy when invocation fails. ASR exposes its own stable `AsrAdapterError.code` for logs/tests before Engine Host wrapping.

## Engine Host integration

F7 proves real Engine Host compatibility by registering each ASR adapter factory into `EngineHost`, loading it with a fake legacy provider, invoking a real `RealtimeFrame`, and verifying:
- request metadata preserved;
- payload identity preserved;
- normalized ASR result returned;
- one failing ASR adapter does not break another host adapter.

## Resource policy

The ASR wrapper itself retains only provider reference/config and normalized result objects. Model memory remains provider-owned. F7 does not load more than Engine Host capacity permits.

Existing lite pack budgets remain authoritative:
- Moonshine ASR estimate ~430 MiB;
- Whisper Tiny ASR estimate ~360 MiB;
- Sherpa Zipformer ASR estimate ~150 MiB.

## Contract `asr/v1`

Metadata/result JSON only; PCM stays out-of-band.

Messages:
- AsrRequestDescriptor;
- AsrWord;
- AsrSegment;
- AsrMetrics;
- AsrResult.

No provider-specific model configuration is compatibility-locked in `asr/v1`.

## Lifecycle/composition

- component `asr` version `1.0.0`;
- stage development -> candidate after F7 gates;
- composition advances to `3.0.0-alpha.4-dev.1`.

ASR remains candidate because F7 unit CI wraps proven providers but does not download real weights through the new wrapper. Release/MegaBench later promotes it after real model invocation on target Windows hardware.
