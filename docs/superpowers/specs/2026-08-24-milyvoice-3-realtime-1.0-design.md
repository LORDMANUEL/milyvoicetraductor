# MilyVoice 3 — Realtime 1.0 Component Design

## Purpose

F5 introduces `realtime 1.0.0` as the timing/backpressure boundary between Audio and downstream inference. Its primary product problem is progressive desynchronization: CPU stalls, browser jitter or network-like arrival variation must not turn a 100 ms audio cadence into an ever-growing subtitle/translation delay.

Realtime does not capture audio, resample, recognize speech, translate text or synthesize speech. It consumes the public Audio v1 shape, validates ordering, computes a sample-derived media timeline and provides bounded buffering.

## Why media time is sample-derived

`capturedMonotonicNs` is evidence about arrival/capture timing. It is useful for jitter and regression detection, but it is not the authoritative media cursor.

For an accepted chunk:

```text
sampleFrames = sampleCount / channels
durationNs = sampleFrames * 1_000_000_000 / sampleRate
mediaStartNs = previous media cursor
next media cursor = mediaStartNs + durationNs
```

This means a 500 ms CPU stall increases observed jitter but does not add 500 ms to every future subtitle. The downstream media position advances by audio duration, not processing delay.

## Audio consumer boundary

Production code uses structural attributes compatible with `audio/v1` / the public `AudioChunk` API:

- source
- sequence_id
- captured_monotonic_ns
- sample_rate
- channels
- sample_count
- sample_format
- discontinuity
- samples payload reference

`mily_realtime` does not import `mily_audio`. Integration tests instantiate the real `mily_audio.AudioIngress` producer and pass its output to Realtime. This proves producer/consumer compatibility while preserving production module independence.

## Timeline state

One `RealtimeTimeline` instance represents one source stream.

State:
- epoch;
- expected next sequence ID;
- media cursor in nanoseconds;
- previous capture timestamp and previous media duration;
- accepted count;
- gap count/events;
- out-of-order count;
- timestamp-regression count;
- maximum observed jitter.

### Accepted order

- first normal chunk must use sequence 0;
- sequence equal to expected is continuous;
- sequence greater than expected is accepted with `gapBefore > 0` and an explicit discontinuity marker;
- sequence lower than expected is rejected as duplicate/out-of-order;
- a monotonic timestamp regression inside one continuous epoch is rejected.

### Explicit discontinuity

An Audio chunk with `discontinuity=true` starts a new epoch and must use sequence 0. Media time restarts at zero for the new epoch. This makes restarts visible instead of silently splicing unrelated clocks.

## Jitter

For continuous adjacent chunks:

```text
arrivalDeltaNs = currentCapturedMonotonicNs - previousCapturedMonotonicNs
expectedDeltaNs = previousChunkDurationNs
jitterNs = abs(arrivalDeltaNs - expectedDeltaNs)
```

Jitter is diagnostic only. It never moves the media cursor.

## Bounded queue

`BoundedRealtimeQueue` owns only buffering, not timeline validation.

Limits:
- maximum chunks;
- maximum buffered media duration.

Policies:
- `rejectNew`: preserve queued audio; refuse the arriving frame when full;
- `dropOldest`: remove the minimum number of oldest frames needed to fit the new frame, record every drop, then accept the new frame.

A single frame larger than `maxBufferedDurationNs` is always rejected because no eviction can make it valid.

No overflow is silent. The caller receives an offer result and queue metrics expose dropped/rejected counts. A later accepted source sequence naturally exposes any lost producer sequence as a timeline gap.

## Payload memory behavior

Realtime stores the payload object by reference and does not copy PCM samples. The queue is bounded by chunk count and media duration, preventing unbounded retention even if downstream ASR slows down.

## Long-run drift gate

A deterministic 60-minute fixture uses 100 ms chunks (36,000 chunks) with synthetic capture jitter/stalls. The final sample-derived media cursor must equal exactly 60 minutes within integer rounding of individual chunks, regardless of capture timestamp jitter.

The test also verifies:
- no progressive timestamp-derived drift;
- gap detection without inventing missing media duration;
- bounded queue depth/duration under sustained producer pressure.

## Component version

- component: `realtime`
- version: `1.0.0`
- contract: `realtime/v1`
- initial stage: `development`, then `candidate` after F5 gates.

Realtime remains candidate after F5. F6 Engine Host becomes its first downstream consumer.

## Audio lifecycle impact

F5 exercises `audio/v1` with the actual Audio producer in integration tests. That satisfies consumer-contract evidence but does not claim physical WASAPI certification. Audio 1.0.0 therefore remains `candidate` until a physical Windows/release gate validates that exact component version.

## Composition

F5 advances the development composition to `3.0.0-alpha.3-dev.1` with Realtime candidate. F6 Engine Host will complete the `3.0.0-alpha.3` composition.

## Non-goals

- ASR segmentation/VAD;
- transcript ordering;
- translation/TTS queues;
- process scheduling;
- audio resampling;
- model selection;
- copying or persisting audio;
- modifying Audio/Compute/Supervisor internals.
