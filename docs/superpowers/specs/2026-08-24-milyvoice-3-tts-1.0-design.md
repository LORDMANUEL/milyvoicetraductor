# MilyVoice 3 — TTS 1.0 Design

## Status and base

F9 starts from `v3/integration` at `cb58f65ebba8cf39e9633d8bd98c15abaa4dc395`, after F8B MT 1.0.0 was merged. MilyVoice 2.1.x remains isolated on `main`.

## Goal

Create `mily-tts 1.0.0` as a lightweight, optional, restartable component that speaks final translations with local OS/browser voices, keeps its own bounded queue, supports per-speaker voice selection, applies optional ducking without stopping capture, reports health, and falls back to subtitles whenever speech is disabled or fails.

## Existing production baseline

The 2.1.x Chromium extension already uses `chrome.tts.speak`, reads `ttsVoiceName` and `speakerVoiceNames`, and emits `tts.started` / `tts.finished` control messages. The local engine already registers synthesized text in `EchoGuard` so matching hypotheses can be ignored temporarily without stopping audio capture.

Two gaps must be closed by F9:

1. the extension currently delegates queueing to Chromium with `enqueue: true`, so pending speech is not bounded by MilyVoice and can drift behind realtime translation;
2. `duckingLevel` is calculated but the offscreen playback gain is never actually reduced/restored.

## Architectural choice

F9 is an extension-local JavaScript component, not a new Python process and not a neural TTS model. The first implementation deliberately reuses voices exposed by Chrome/Edge/Windows. This keeps the product memory budget small and avoids duplicating synthesis stacks.

The portable boundary is `tts/v1`. A future Desktop-native implementation may consume the same contract without changing consumers.

Implementation ownership:

- `apps/extension/tts/controller.js`: pure bounded queue/state machine and deterministic policy;
- `apps/extension/tts.js`: Chromium adapter and settings/voice resolution;
- `apps/extension/offscreen.js`: playback ducking actuator only;
- `apps/extension/background.js`: lifecycle forwarding only;
- `apps/extension/tts/COMPONENT.json`: component identity;
- `contracts/tts/v1/**`: public contract.

TTS does not own ASR, MT, session persistence, model selection, or audio capture.

## Queue policy

TTS 1.0.0 has one active utterance and at most three pending utterances.

- `maxPending = 3`.
- `maxAgeMs = 4000` for pending speech.
- A new item never interrupts the active utterance solely because the queue is full.
- When the pending queue is full, the oldest pending item is dropped before the new one is appended.
- A pending item older than `maxAgeMs` is skipped before synthesis.
- Dropped/stale items emit a machine-readable reason to diagnostics but subtitles remain visible.
- The adapter calls Chromium with `enqueue: false`; MilyVoice owns sequencing.

This policy prevents TTS latency from growing monotonically during fast conversation.

## Voice policy

Voice selection order is deterministic:

1. speaker-specific voice from `speakerVoiceNames[speakerId]`;
2. global `ttsVoiceName`;
3. operating-system/browser default voice for the requested language.

Valid speaker IDs remain `speaker-[a-z]`. F9 never infers gender, age, identity, or other sensitive attributes from audio. Automatic distinct voices may only be based on user configuration or available non-sensitive voice identifiers.

Language defaults:

- `es` / `es-*` -> `es-ES`;
- `en` / `en-*` -> `en-US`;
- `zh` / `zh-*` -> `zh-CN`;
- another explicit BCP-47-like language is passed through after normalization;
- missing target language defaults to Spanish because the current promoted MT routes target Spanish.

## Ducking

The offscreen document owns the playback gain node because it already owns tab audio reinjection.

- normal gain: `1.0`;
- configured ducking gain is clamped to `0.05..1.0`;
- `TTS_STARTED` applies ducking when enabled;
- `TTS_FINISHED`, cancellation, error, capture stop, and cleanup restore gain to `1.0`;
- ASR capture and PCM transmission continue while ducking is active.

Ducking changes only local playback volume. It never pauses or destroys the capture graph.

## Anti-feedback

On actual TTS start, background forwards synthesized text to offscreen. Offscreen sends `tts.started` to the local engine. The existing server calls `pipeline.register_tts(text)`, and the existing `EchoGuard` suppresses hypotheses sufficiently similar to recently synthesized text for a short TTL.

F9 must preserve this chain. The TTS component does not duplicate ASR filtering.

## Failure and restart behavior

TTS is optional. Any of the following must leave subtitles and ASR/MT operating:

- TTS disabled by the user;
- empty translation;
- runtime `chrome.tts` error;
- cancelled/interrupted utterance;
- queue overflow or stale pending utterance;
- TTS service-worker state reset/restart.

Every terminal path restores ducking. `chrome.tts.stop()` is allowed to clear speech, but stopping TTS must never send `audio.stop`, stop MediaStream tracks, close the WebSocket, unload ASR, or unload MT.

## `tts/v1` contract

`tts/v1` is JSON and additive-within-major. It exposes only portable data:

- `TtsRequest`: request ID, utterance ID, text, target language, optional speaker ID, voice ID and ducking preference;
- `TtsLifecycleEvent`: request/utterance IDs, state, reason, speaker ID and queue depth;
- `TtsSnapshot`: enabled/health state, active flag, pending count, dropped count and last error reason.

The contract does not expose `chrome.tts`, extension tab IDs, AudioContext nodes, model paths, or browser internals.

## Health model

TTS reports:

- `disabled`: feature intentionally off;
- `healthy`: enabled and idle/playing without unresolved runtime error;
- `degraded`: enabled but the latest synthesis failed or pending work was dropped.

A later successful utterance can return health to `healthy`.

## Resource behavior

F9 adds no model weights, Python process, native runtime, GPU requirement, or network request. Queue state is bounded to four utterances total (one active plus three pending). Text payloads are short-lived and are not persisted by TTS.

## Lifecycle

TTS 1.0.0 ends this phase as `candidate`, not `certified`. CI can prove queue policy, contract, failure isolation, ducking state transitions and anti-feedback wiring. Promotion to `certified` requires a real Windows/Chromium hardware run proving audible synthesis and ducking with installed voices.

## Composition

Successful F9 advances the 3.x composition from `3.0.0-alpha.4-dev.3` to `3.0.0-alpha.4-dev.4` and adds:

```json
{"id":"tts","version":"1.0.0","contract":"tts/v1","stage":"candidate","required":false}
```

TTS remains optional in alpha.4; subtitles are the required output path.

## Acceptance gates

1. Pure controller tests pass on Node 22 in Linux and Windows.
2. Queue never contains more than three pending utterances.
3. Overflow drops oldest pending, not active speech.
4. Stale pending speech is skipped.
5. `chrome.tts.speak` is called with `enqueue: false`.
6. Voice selection honors speaker -> global -> OS default order.
7. Empty/disabled/error TTS leaves subtitle dispatch independent.
8. Ducking applies and restores deterministically.
9. `tts.started` still registers synthesized text in the existing engine anti-feedback path.
10. TTS stop/failure never stops capture, ASR, MT, Engine Host, or Realtime.
11. `tts/v1` passes Contracts Kernel and compatibility lock checks.
12. Updated composition passes Supervisor/Contracts and all affected module gates.
