# MilyVoice 3 — Audio 1.0 Component Design

## Purpose

F4 extracts the already working PCM/WASAPI behavior into an independently versioned `audio 1.0.0` component. It does not rewrite the 2.1.x AI package and does not modify MilyCompute. The 2.1.x files remain untouched while the 3.x line gains a clean `audio/v1` boundary.

## Existing behavior reused

The current implementation already has:

- PCM16 LE decode and normalization to float32;
- bounded ASR window buffering with overlap;
- Windows WASAPI loopback capture;
- stereo-to-mono conversion;
- resampling to 16 kHz;
- silent-default probing and failover to another active loopback device;
- fake-backend unit coverage.

F4 copies this proven behavior into the new component, then adds sequencing/timing metadata required by F5 Realtime. The legacy 2.1.x source is not edited during this extraction.

## Package boundary

```text
services/audio/
  pyproject.toml
  COMPONENT.json
  mily_audio/
    __init__.py
    pcm.py
    loopback.py
    stream.py
  tests/
```

The package depends only on the pinned NumPy already certified by the 2.1 runtime (`numpy==2.5.2`). `PyAudioWPatch==0.2.12.8` is a Windows runtime extra and remains lazily imported so Linux tests and non-loopback consumers do not load it.

## Canonical audio format

The v1 processing format is:

- mono;
- float32 normalized samples in [-1, 1] where the source permits;
- target sample rate 16,000 Hz for ASR ingress;
- chunk payload transported as binary/in-memory samples, not JSON arrays.

The language-neutral JSON contract carries metadata only; payload transport is explicitly out-of-band for performance.

## Audio source identities

`AudioSourceKind`:

- `microphone`
- `systemLoopback`
- `browserTab`
- `mediaFile`

All sources converge on the same chunk descriptor before entering Realtime/ASR.

## Sequencing and clock

Every emitted chunk gets:

- `sequenceId`, starting at 0 and strictly increasing per source stream;
- `capturedMonotonicNs`, sampled from a monotonic clock;
- source identity;
- sample rate;
- channels;
- sample count;
- discontinuity flag.

Wall-clock timestamps are not used to order realtime audio. F5 will use sequence IDs and monotonic timestamps to detect loss/jitter without allowing clock adjustments to create sentence drift.

## AudioIngress

`AudioIngress` accepts already captured float PCM from microphone/browser/media adapters and attaches canonical metadata. It rejects invalid sample rate/channels and non-finite samples. This gives browser/microphone/media a real Audio-module entry point without forcing this package to own every platform capture API.

## WASAPI source

`WasapiLoopbackSource` remains responsible for the physical Windows system-audio adapter. It returns normalized float samples and retains conservative failover: a silent default device can switch only after another loopback produces measurable activity.

## Buffering

`PcmChunkBuffer` retains the existing overlap model. F4 adds stress coverage proving repeated 100 ms ingress does not cause unbounded retained samples. F5 owns transport queue backpressure; F4 owns only local window buffering.

## `audio/v1`

Contract enums:

- `AudioSourceKind`
- `SampleFormat` (`float32`)

Contract messages:

- `AudioChunkDescriptor`
- `AudioDeviceInfo`

`AudioChunkDescriptor` fields:

- source
- sequenceId
- capturedMonotonicNs
- sampleRate
- channels
- sampleFormat
- sampleCount
- discontinuity

Invariants:

1. sequence IDs are strictly increasing within one stream;
2. monotonic timestamps never intentionally decrease;
3. sample count describes the out-of-band payload;
4. normalized ASR ingress is mono 16 kHz float32;
5. a missing/failed optional capture adapter cannot change another component's state.

## Certification

Audio 1.0.0 remains `candidate` after F4 because CI uses a fake WASAPI device rather than physical hardware. It may move to `certified`/`frozen` after F5 consumes `audio/v1` and a Windows physical/release gate validates the same component version.
