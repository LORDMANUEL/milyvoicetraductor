# MilyVoice 3 — F8B MT 1.0.0 Design

## Goal
Create a provider-neutral Machine Translation component that consumes the deterministic output of `linguistic/v1`, delegates inference to the existing translation provider factory, and returns a stable `mt/v1` result without modifying legacy providers.

## Certified scope for 1.0.0 candidate
Only routes already backed by current local model packs are promoted:

- `en -> es`: `marian-ct2` via the existing Marian Tiny/OPUS-MT path.
- `zh -> es`: `marian-cascade-ct2` via the existing ZH->EN->ES cascade.

`es -> en` and `es -> zh` are intentionally not advertised because the repository currently has no corresponding model packs. The contract remains route-extensible for future versions.

## Responsibilities
MT owns:

- validation of prepared linguistic input;
- lazy construction of an existing translation provider;
- translation invocation;
- normalized elapsed-time metrics;
- quality and source-target fidelity checks using `mily_linguistic`;
- deterministic rejection of empty/invalid output;
- lifecycle methods compatible with Engine Host.

MT does not own:

- audio or ASR;
- model download or selection;
- CPU/GPU policy;
- terminology rewriting;
- conversation persistence;
- model implementation.

## Input boundary
The adapter accepts an object compatible with `PreparedTranslationInput`:

- `text`
- `source_language`
- `target_language`
- `segments`
- `terminology`
- `context`

For Engine Host invocation, the prepared input is supplied through the request frame/payload while request metadata carries a stable `utteranceId`.

## Provider integration
Production defaults are lazy imports of:

- `mily_ai.provider_factory.build_translation_provider`
- `mily_ai.cpu_budget.detect_cpu_budget`

The adapter injects `provider` from its concrete class into the configured component and rejects conflicting provider declarations.

Concrete candidate adapters:

- `MarianEnEsMtAdapter`: engine id `marian-en-es`, provider `marian-ct2`, exact route `en -> es`.
- `MarianZhEsCascadeMtAdapter`: engine id `marian-zh-es`, provider `marian-cascade-ct2`, exact route `zh -> es`.

## Linguistic integration
Before inference, MT requires normalized non-empty source text and exact route consistency. It passes the prepared `text` to the provider and does not synthesize a prompt from context or terminology in 1.0.0.

After inference, MT runs:

- `analyze_translation_quality(target_text)`;
- `analyze_source_target_fidelity(source_text, target_text, source_language, target_language)`.

A translation that fails either guard is returned as a structured rejected result rather than silently replaced with source text.

## Result
`MtResult` contains:

- request/utterance ids;
- engine/provider ids;
- source/target language;
- source and target text;
- accepted boolean;
- reason (`OK`, quality/fidelity reason, or stable adapter error reason);
- quality report;
- fidelity report;
- elapsed milliseconds.

No audio or model paths are serialized into the public result.

## Memory and latency
The wrapper is stdlib-only until `load()` and holds exactly one provider instance. Prepared strings/tuples are consumed without building a second conversation history. No queue, cache, batching layer, or model copy is added.

## Failure isolation
Configuration errors occur before provider construction where possible. Provider exceptions propagate to Engine Host, which already owns adapter health isolation. Invalid translation output becomes a deterministic MT result when inference itself succeeded.

## Tests
1. RED adapter module missing.
2. Load/invoke/unload with fake provider.
3. Route/provider conflict validation.
4. Quality/fidelity rejection.
5. Engine Host integration with Linguistic prepared input.
6. Legacy factory/model-pack compatibility for the two promoted routes.
7. `mt/v1` contract + compatibility lock + fixtures.
8. lifecycle `development -> candidate`.
9. composition promotion only after exact-head cross-gates.

## Lifecycle
MT 1.0.0 ends as `candidate`. Real model inference/MegaBench on target hardware is required before `certified`.
