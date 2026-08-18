# CPU Realtime Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reducir la latencia y evitar atraso acumulativo en CPU usando el pack existente `Whisper Small + M2M100 CTranslate2 INT8`, sin sustituir modelos ni degradar silenciosamente la funcionalidad.

**Architecture:** Separar ingestión de audio, ASR, estabilización de parciales y traducción en etapas con colas limitadas. Configurar explícitamente threads de CTranslate2/Faster-Whisper según un presupuesto de CPU y usar control adaptativo para disminuir trabajo parcial antes de permitir backlog. El canal de audio negociará PCM binario para eliminar Base64/JSON del camino caliente.

**Tech Stack:** Python 3.13, FastAPI/WebSocket, NumPy, Faster-Whisper, CTranslate2, Rust/Tauri para hardware/configuración, Chromium MV3 AudioWorklet.

**Spec:** `docs/superpowers/specs/2026-08-18-milyvoice-1.0.5-master-spec.md`

## Global Constraints

- Mantener `realtime-m2m100` como pack default: `Systran/faster-whisper-small` + `facebook/m2m100_418M` convertido a CTranslate2 INT8.
- No añadir otro modelo ASR/traductor en este plan.
- CPU sin GPU es ruta de primera clase; CUDA sigue siendo opcional.
- No abrir consola visible en Windows.
- Audio/transcripción/traducción permanecen locales.
- No almacenar audio/transcripción sin consentimiento.
- No inferir género/identidad desde la voz.
- No permitir que la cola crezca de forma monotónica; los parciales se coalescen antes de acumular atraso.
- `word_timestamps` permanece apagado en conversación y solo se habilita en trabajo final de karaoke.
- Cada cambio debe pasar tests antes de continuar.

## Evidencia del cuello de botella actual

- `RealtimePipeline` acumula ventanas rígidas de 2.0 s y ejecuta ASR y traducción secuencialmente.
- `server.py` espera `pipeline.push()` antes de volver a consumir el siguiente mensaje de audio.
- `WhisperModel` se crea sin `cpu_threads` ni `num_workers`; Faster-Whisper permite ambos parámetros y documenta que `cpu_threads` controla threads CPU y `num_workers` la concurrencia real.
- `M2M100CTranslate2Translator` fija `inter_threads=1` pero no fija `intra_threads`.
- CTranslate2 recomienda INT8 en CPU y evitar que `inter_threads * intra_threads` supere núcleos físicos.
- La extensión manda PCM como Base64 dentro de JSON cada 100 ms.

Referencias primarias:

- Faster-Whisper README: `https://github.com/SYSTRAN/faster-whisper/blob/master/README.md`
- Faster-Whisper `WhisperModel`: `https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py`
- CTranslate2 performance: `https://github.com/OpenNMT/CTranslate2/blob/master/docs/performance.md`

---

### Task 1: Presupuesto de CPU explícito

**Files:**
- Create: `services/ai/mily_ai/cpu_budget.py`
- Modify: `services/ai/mily_ai/providers.py`
- Modify: `services/ai/mily_ai/pipeline.py`
- Test: `services/ai/tests/test_cpu_budget.py`
- Test: `services/ai/tests/test_realtime_optimization.py`

**Interfaces:**
- Produces: `CpuBudget(profile, physical_cores, asr_threads, translation_threads, parallel_stages)`
- Produces: `detect_cpu_budget(profile: str, physical_cores: int | None = None) -> CpuBudget`
- Consumes: `CpuBudget` in `FasterWhisperAsr` and `M2M100CTranslate2Translator`.

- [ ] **Step 1: Write failing scheduler tests**

```python
from mily_ai.cpu_budget import detect_cpu_budget


def test_cpu_budget_never_oversubscribes_physical_cores():
    for cores in range(1, 17):
        budget = detect_cpu_budget("balanced", physical_cores=cores)
        if budget.parallel_stages:
            assert budget.asr_threads + budget.translation_threads <= cores
        assert budget.asr_threads >= 1
        assert budget.translation_threads >= 1


def test_small_cpu_disables_parallel_compute_stages():
    budget = detect_cpu_budget("balanced", physical_cores=1)
    assert budget.parallel_stages is False
    assert budget.asr_threads == 1
    assert budget.translation_threads == 1
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
PYTHONPATH=services/ai python -m unittest services.ai.tests.test_cpu_budget -v
```

Expected: FAIL because `mily_ai.cpu_budget` does not exist.

- [ ] **Step 3: Implement CPU budget**

Implement `CpuBudget` as frozen dataclass. Resolve core count in this order:

1. explicit `physical_cores` argument;
2. `MILY_PHYSICAL_CPUS` environment value if valid;
3. conservative fallback `max(1, (os.cpu_count() or 1) // 2)`.

Profiles:

```python
if profile == "light":
    compute = min(2, physical)
elif profile == "max":
    compute = physical
else:
    compute = max(1, physical - 1)

parallel = compute >= 2
if not parallel:
    asr_threads = translation_threads = 1
else:
    asr_threads = max(1, round(compute * 0.65))
    translation_threads = max(1, compute - asr_threads)
```

Normalize any overflow by reducing `asr_threads` first until the sum is `<= physical`.

- [ ] **Step 4: Wire threads into model constructors**

`FasterWhisperAsr` must pass:

```python
WhisperModel(
    str(self.model_path),
    device=device,
    compute_type=compute_type,
    cpu_threads=budget.asr_threads if device == "cpu" else 0,
    num_workers=1,
    local_files_only=True,
)
```

`M2M100CTranslate2Translator` must pass:

```python
ctranslate2.Translator(
    str(self.model_path),
    device=device,
    compute_type=compute_type,
    inter_threads=1,
    intra_threads=budget.translation_threads if device == "cpu" else 0,
)
```

Keep `beam_size=1`.

- [ ] **Step 5: Run tests GREEN**

```bash
PYTHONPATH=services/ai python -m unittest services.ai.tests.test_cpu_budget services.ai.tests.test_realtime_optimization -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/ai/mily_ai/cpu_budget.py services/ai/mily_ai/providers.py services/ai/mily_ai/pipeline.py services/ai/tests/test_cpu_budget.py services/ai/tests/test_realtime_optimization.py
git commit -m "perf: budget CPU threads for realtime models"
```

---

### Task 2: PCM binario y eliminación de Base64 del camino caliente

**Files:**
- Modify: `apps/extension/offscreen.js`
- Modify: `services/ai/mily_ai/server.py`
- Modify: `services/ai/mily_ai/audio.py`
- Modify: `services/ai/mily_ai/protocol.py`
- Modify: `scripts/test_extension.py`
- Test: `services/ai/tests/test_audio.py`
- Create: `services/ai/tests/test_binary_audio_protocol.py`

**Interfaces:**
- WebSocket JSON `client.hello` adds capability `binaryPcm: true`.
- Binary frame payload: little-endian signed PCM16 mono, 16 kHz.
- JSON `audio.chunk` remains fallback for compatibility.
- Produces: `decode_pcm16_bytes(raw: bytes) -> numpy.ndarray`.

- [ ] **Step 1: Write failing binary decoder tests**

```python
import struct
import numpy as np
from mily_ai.audio import decode_pcm16_bytes


def test_binary_pcm_decoder_returns_float32_without_python_sample_list():
    raw = struct.pack("<3h", -32768, 0, 32767)
    samples = decode_pcm16_bytes(raw)
    assert isinstance(samples, np.ndarray)
    assert samples.dtype == np.float32
    np.testing.assert_allclose(samples, [-1.0, 0.0, 32767 / 32768], atol=1e-6)
```

- [ ] **Step 2: Run RED**

```bash
PYTHONPATH=services/ai python -m unittest services.ai.tests.test_binary_audio_protocol -v
```

Expected: FAIL because `decode_pcm16_bytes` does not exist.

- [ ] **Step 3: Implement zero-copy-oriented decoder**

Use:

```python
pcm = np.frombuffer(raw, dtype="<i2")
return pcm.astype(np.float32) / 32768.0
```

Validate non-empty, even byte length and existing maximum chunk size.

- [ ] **Step 4: Teach server to accept bytes and text**

Replace text-only receive with `message = await websocket.receive()`. Route `message["bytes"]` to binary PCM only after a valid `client.hello`. Route `message["text"]` through existing protocol parser.

- [ ] **Step 5: Change extension hot path**

In `offscreen.js`, after WebSocket opens and capability is active, send `event.data` directly:

```javascript
websocket.send(event.data);
```

Do not call `arrayBufferToBase64` on the binary route. Retain Base64 fallback only when binary capability is unavailable.

- [ ] **Step 6: Add source guard**

`scripts/test_extension.py` must assert the offscreen hot path contains `websocket.send(event.data)` and does not require Base64 for negotiated binary mode.

- [ ] **Step 7: Run GREEN**

```bash
PYTHONPATH=services/ai python -m unittest services.ai.tests.test_audio services.ai.tests.test_binary_audio_protocol -v
python scripts/test_extension.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add apps/extension/offscreen.js services/ai/mily_ai/server.py services/ai/mily_ai/audio.py services/ai/mily_ai/protocol.py scripts/test_extension.py services/ai/tests/test_audio.py services/ai/tests/test_binary_audio_protocol.py
git commit -m "perf: stream binary pcm to local engine"
```

---

### Task 3: Ring buffer, energy gate y segmentación adaptativa

**Files:**
- Modify: `services/ai/mily_ai/audio.py`
- Create: `services/ai/mily_ai/streaming.py`
- Test: `services/ai/tests/test_audio.py`
- Create: `services/ai/tests/test_streaming_segmenter.py`

**Interfaces:**
- Produces: `AudioLevel(rms, peak, silent_ms)`.
- Produces: `StreamingSegmenter.push(samples) -> list[AudioSnapshot]`.
- `AudioSnapshot.kind`: `partial` or `final`.
- `AudioSnapshot.samples`: NumPy float32.
- Conversation defaults: first decode near 0.9 s of speech, subsequent partial snapshot no more often than 0.45 s, final after approximately 0.22–0.30 s silence, hard utterance cap 2.4 s.
- Music defaults: longer windows and less aggressive silence cutoff.

- [ ] **Step 1: Write failing tests for silence bypass**

```python
import numpy as np
from mily_ai.streaming import StreamingSegmenter


def test_silence_does_not_create_asr_snapshot():
    segmenter = StreamingSegmenter(sample_rate=16000, mode="conversation")
    for _ in range(20):
        assert segmenter.push(np.zeros(1600, dtype=np.float32)) == []
    assert segmenter.level.silent_ms >= 1900
```

- [ ] **Step 2: Write failing test for adaptive speech emission**

Feed 100 ms chunks of constant non-zero synthetic speech amplitude and assert no snapshot before minimum speech duration, then a `partial`, then a `final` after silence.

- [ ] **Step 3: Run RED**

```bash
PYTHONPATH=services/ai python -m unittest services.ai.tests.test_streaming_segmenter -v
```

Expected: FAIL because module is missing.

- [ ] **Step 4: Implement segmenter**

Use chunk-level RMS and peak. Keep an internal deque of NumPy arrays and sample count. Do not append long runs of silence to inference buffers. Add short pre-roll so initial consonants are preserved when speech starts.

- [ ] **Step 5: Keep Faster-Whisper VAD as second line**

Do not remove `vad_filter=True`. The energy gate skips obvious silence; Silero VAD remains responsible for speech boundaries inside audio actually sent to Whisper.

Conversation VAD target to benchmark first:

```python
vad_parameters={"min_silence_duration_ms": 220, "speech_pad_ms": 60}
```

Music mode keeps a larger silence threshold and padding.

- [ ] **Step 6: Run GREEN**

```bash
PYTHONPATH=services/ai python -m unittest services.ai.tests.test_audio services.ai.tests.test_streaming_segmenter -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add services/ai/mily_ai/audio.py services/ai/mily_ai/streaming.py services/ai/tests/test_audio.py services/ai/tests/test_streaming_segmenter.py
git commit -m "perf: segment realtime speech before whisper"
```

---

### Task 4: Parciales estables sin retraducir cada ventana

**Files:**
- Create: `services/ai/mily_ai/stabilizer.py`
- Modify: `services/ai/mily_ai/providers.py`
- Modify: `services/ai/mily_ai/pipeline.py`
- Create: `services/ai/tests/test_stabilizer.py`
- Modify: `services/ai/tests/test_realtime_optimization.py`

**Interfaces:**
- Produces: `StableText(partial, newly_stable, committed)`.
- Produces: `HypothesisStabilizer.update(text: str, final: bool) -> StableText`.
- ASR emits original partial quickly; translation only consumes `newly_stable`/committed phrase spans.

- [ ] **Step 1: Write RED stability test**

```python
from mily_ai.stabilizer import HypothesisStabilizer


def test_prefix_must_repeat_before_becoming_stable():
    s = HypothesisStabilizer()
    first = s.update("I am going", final=False)
    assert first.newly_stable == ""
    second = s.update("I am going to work", final=False)
    assert second.newly_stable == "I am going"
```

- [ ] **Step 2: Add final commit test**

Final input must commit the remaining suffix once and never emit duplicate stable text.

- [ ] **Step 3: Implement normalized token-prefix agreement**

Tokenize by whitespace after normalization. Compare current and previous hypothesis. Commit longest common prefix not previously emitted. On final, commit remaining current hypothesis.

- [ ] **Step 4: Lock detected language**

When source is explicit `en` or `zh`, pass it on every ASR call and skip detection. When source is `auto`, preserve current confidence lock behavior; after lock, do not re-run language detection for every window.

- [ ] **Step 5: Keep word timestamps out of partial path**

`word_timestamps=False` for conversation partial/final transcription. Karaoke will request a secondary alignment/final pass later, outside this CPU-critical plan.

- [ ] **Step 6: Run GREEN**

```bash
PYTHONPATH=services/ai python -m unittest services.ai.tests.test_stabilizer services.ai.tests.test_realtime_optimization -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add services/ai/mily_ai/stabilizer.py services/ai/mily_ai/providers.py services/ai/mily_ai/pipeline.py services/ai/tests/test_stabilizer.py services/ai/tests/test_realtime_optimization.py
git commit -m "perf: stabilize partial whisper hypotheses"
```

---

### Task 5: Desacoplar ASR y traducción con backpressure

**Files:**
- Create: `services/ai/mily_ai/realtime_session.py`
- Modify: `services/ai/mily_ai/server.py`
- Modify: `services/ai/mily_ai/pipeline.py`
- Create: `services/ai/tests/test_realtime_session.py`
- Modify: `services/ai/tests/test_server.py`

**Interfaces:**
- Produces: `RealtimeSessionRunner.start()` / `push_audio()` / `finish()`.
- Internal ASR executor: exactly one inference job at a time.
- Internal translation executor: exactly one inference job at a time.
- Pending partial ASR snapshots are replaceable/coalesced; final utterances are never dropped.
- Translation queue translates stable text only and coalesces obsolete partial work.

- [ ] **Step 1: Write RED test proving ingress never waits for slow ASR**

Use fake ASR that sleeps 200 ms. Push twenty 100 ms audio chunks and assert `push_audio()` calls complete without waiting 200 ms each.

- [ ] **Step 2: Write RED test for partial coalescing**

Queue three partial snapshots while ASR is busy and assert only the newest pending partial is decoded after current work; final snapshot must still run.

- [ ] **Step 3: Implement dedicated worker queues**

Use `asyncio.Queue` for control and one-slot replaceable partial state. Use named `ThreadPoolExecutor(max_workers=1)` instances instead of the process-wide default executor.

- [ ] **Step 4: Server consumes WebSocket continuously**

`audio.chunk`/binary audio should call `runner.push_audio(samples)` and return to receive loop immediately. Output events come from runner callback/async output queue.

- [ ] **Step 5: Preserve session recorder semantics**

Only final translated segments enter persistent recorder. Partial text remains ephemeral.

- [ ] **Step 6: Run GREEN**

```bash
PYTHONPATH=services/ai python -m unittest services.ai.tests.test_realtime_session services.ai.tests.test_server -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add services/ai/mily_ai/realtime_session.py services/ai/mily_ai/server.py services/ai/mily_ai/pipeline.py services/ai/tests/test_realtime_session.py services/ai/tests/test_server.py
git commit -m "perf: pipeline asr and translation concurrently"
```

---

### Task 6: Optimizar M2M100 para frase corta interactiva

**Files:**
- Modify: `services/ai/mily_ai/providers.py`
- Modify: `services/ai/tests/test_realtime_optimization.py`
- Create: `services/ai/tests/test_translation_scheduler.py`

**Interfaces:**
- `M2M100CTranslate2Translator.translate()` keeps one warmed translator/tokenizer.
- Translation receives only stable phrase chunks.
- No beam search >1.

- [ ] **Step 1: Write RED constructor test**

Mock `ctranslate2.Translator` and assert CPU construction receives `inter_threads=1` and explicit `intra_threads=budget.translation_threads`.

- [ ] **Step 2: Explicitly disable score work**

Call `translate_batch` with:

```python
beam_size=1,
return_scores=False,
```

Keep one input phrase per interactive call. Do not increase batch size in realtime mode because the objective is latency, not offline throughput.

- [ ] **Step 3: Bound runaway decoding**

Derive a conservative decoding cap from source token count:

```python
max_len = max(32, min(96, len(source) * 2 + 12))
```

Pass `max_decoding_length=max_len`.

- [ ] **Step 4: Warm model at session start**

After model load, execute one tiny local translation warm-up outside the audio critical path. Record warm-up latency but do not emit its output.

- [ ] **Step 5: Run GREEN**

```bash
PYTHONPATH=services/ai python -m unittest services.ai.tests.test_realtime_optimization services.ai.tests.test_translation_scheduler -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/ai/mily_ai/providers.py services/ai/tests/test_realtime_optimization.py services/ai/tests/test_translation_scheduler.py
git commit -m "perf: tune m2m100 for interactive translation"
```

---

### Task 7: Control adaptativo de latencia

**Files:**
- Create: `services/ai/mily_ai/latency.py`
- Modify: `services/ai/mily_ai/realtime_session.py`
- Modify: `services/ai/mily_ai/server.py`
- Create: `services/ai/tests/test_latency_controller.py`

**Interfaces:**
- Produces: `LatencySnapshot(audio_queue_ms, asr_ms, translation_ms, real_time_factor, state)`.
- States: `healthy`, `pressure`, `overloaded`.
- Produces event `pipeline.metrics`.

- [ ] **Step 1: Write RED state transition tests**

Healthy: queue <300 ms and RTF <0.70.

Pressure: queue >=300 ms or RTF >=0.70.

Overloaded: queue >=1200 ms or RTF >=1.0 for multiple observations.

- [ ] **Step 2: Implement EWMA measurements**

Use monotonic clocks. Keep EWMA for ASR and translation. Never write transcript/audio into metrics.

- [ ] **Step 3: Implement degradation policy**

`healthy`:
- partial decode interval about 450 ms.

`pressure`:
- increase partial interval toward 650 ms;
- do not request word timestamps;
- coalesce translation partial work.

`overloaded`:
- increase partial interval toward 900 ms;
- suppress translation of intermediate partials and translate final/stable phrase only;
- never discard final utterances;
- emit UI warning `CPU al límite; priorizando tiempo real`.

- [ ] **Step 4: Recovery**

Require several healthy observations before returning to a faster mode to avoid oscillation.

- [ ] **Step 5: Run GREEN**

```bash
PYTHONPATH=services/ai python -m unittest services.ai.tests.test_latency_controller -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/ai/mily_ai/latency.py services/ai/mily_ai/realtime_session.py services/ai/mily_ai/server.py services/ai/tests/test_latency_controller.py
git commit -m "perf: adapt realtime workload to cpu pressure"
```

---

### Task 8: Estado de audio y métricas visibles

**Files:**
- Modify: `apps/extension/offscreen.js`
- Modify: `apps/extension/popup.js`
- Modify: `apps/desktop/src/lib/api.ts`
- Modify: `apps/desktop/src/App.svelte`
- Modify: `services/ai/mily_ai/server.py`
- Test: frontend tests covering engine events.

**Interfaces:**
- Event: `audio.level { rms, peak, silentMs, source }`.
- Event: `pipeline.metrics { audioQueueMs, asrMs, translationMs, realTimeFactor, state }`.

- [ ] **Step 1: Add failing frontend tests**

Assert UI distinguishes:
- session connected with signal → `Audio detectado`;
- active but silent → `Silencio`;
- no useful signal beyond threshold → `No se detecta audio`;
- overloaded metrics → `CPU al límite; priorizando tiempo real`.

- [ ] **Step 2: Emit level events at low frequency**

Do not send an event every 100 ms to UI. Aggregate and emit approximately 4 times per second.

- [ ] **Step 3: Render local metrics**

Show compact values only when diagnostics/performance panel is expanded. Normal UI should show human-readable state, not implementation jargon.

- [ ] **Step 4: Run frontend GREEN**

```bash
npm run typecheck
npm test
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/extension/offscreen.js apps/extension/popup.js apps/desktop/src/lib/api.ts apps/desktop/src/App.svelte services/ai/mily_ai/server.py
git commit -m "feat: expose realtime audio and cpu health"
```

---

### Task 9: Benchmark reproducible y criterios de rendimiento

**Files:**
- Create: `scripts/benchmark_realtime_cpu.py`
- Create: `services/ai/tests/test_realtime_backpressure.py`
- Modify: `installer/windows/test-realtime-model.ps1`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Benchmark output JSON contains only timings/configuration, never transcript content unless test fixture is synthetic.
- Fields: `profile`, `physicalCores`, `asrThreads`, `translationThreads`, `audioQueueP50Ms`, `audioQueueP95Ms`, `asrP50Ms`, `asrP95Ms`, `translationP50Ms`, `translationP95Ms`, `rtf`.

- [ ] **Step 1: Add deterministic mock pressure test**

Simulate 180 seconds of 100 ms audio chunks with fake providers slower than realtime partial cadence. Assert pending partial work stays bounded and final segments are not lost.

- [ ] **Step 2: Add real-pack timing to main-only gate**

Extend `test-realtime-model.ps1` to record cold-load, warmed ASR and translation timings. Do not fail CI on a fixed millisecond threshold because GitHub runner hardware varies; fail only on functional regression, unbounded queue or invalid metrics.

- [ ] **Step 3: Define release acceptance on target CPU**

A user-facing CPU validation run is acceptable when:
- 3 minutes of fast English do not cause monotonically growing audio queue;
- RTF stays below 1.0 after warm-up for the chosen profile;
- subtitle delay recovers after temporary CPU pressure instead of accumulating indefinitely;
- UI remains responsive.

- [ ] **Step 4: Run all AI tests**

```bash
PYTHONPATH=services/ai python -m unittest discover -s services/ai/tests -v
python -m compileall -q services/ai
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/benchmark_realtime_cpu.py services/ai/tests/test_realtime_backpressure.py installer/windows/test-realtime-model.ps1 .github/workflows/ci.yml
git commit -m "test: benchmark realtime cpu pipeline"
```

---

### Task 10: Full regression and release gate before universal-audio features

**Files:**
- No new production files unless a failing test exposes a regression.

**Interfaces:**
- This task produces a green optimized CPU baseline that later plans for universal capture, speakers/TTS and karaoke consume.

- [ ] **Step 1: Run repository guards**

```bash
python scripts/test_release_version.py
python scripts/verify_source.py
python scripts/privacy_scan.py .
python scripts/test_extension.py
python scripts/test_site.py
```

Expected: PASS.

- [ ] **Step 2: Run frontend**

```bash
npm run typecheck
npm test
npm run build
```

Expected: PASS.

- [ ] **Step 3: Run Python**

```bash
PYTHONPATH=services/ai python -m unittest discover -s services/ai/tests -v
python -m compileall -q services/ai
```

Expected: PASS.

- [ ] **Step 4: Run Rust**

```bash
cargo fmt --all -- --check
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
```

Expected: PASS.

- [ ] **Step 5: Windows release gates**

CI must pass:
- private Python runtime build and hash verification;
- installed runtime/bridge registration flow;
- Windows Rust tests/Clippy;
- Desktop release;
- `IMAGE_SUBSYSTEM_WINDOWS_GUI` verification;
- Tauri NSIS 1.0.5;
- actual generated NSIS installation;
- extension ZIP;
- SHA-256 artifact.

- [ ] **Step 6: Do not merge to main yet**

This optimized CPU baseline remains in `pruebas`. Universal capture, speakers/TTS and video/karaoke are implemented in their own follow-on plans against this green baseline. `main` receives the complete user-approved feature set only after those plans also pass their gates.

## Expected CPU gains by source of waste

This plan does not promise a fixed percentage before benchmarking. It attacks measurable waste in this order:

1. **Under/incorrect thread allocation:** explicit CPU budget instead of library defaults.
2. **Base64/JSON audio overhead:** binary PCM frames.
3. **Silence work:** energy gate before Whisper while retaining Silero VAD.
4. **2 s rigid wait:** adaptive early partial snapshots.
5. **Repeated partial inference/translation:** prefix stabilization and coalescing.
6. **Serial ASR→translation:** independent workers under one core budget.
7. **Backlog growth:** latency controller reduces optional work before the app falls behind.
8. **Cold start:** warm loaded models before first real utterance.

## Follow-on plans required by the master spec

After this CPU plan is green, create and execute independently:

1. `universal-audio-capture`: browser tabs + WASAPI loopback + microphone + health/fallback.
2. `speakers-and-tts`: speaker embeddings/clustering, dominant/fixed speaker, colors, Windows TTS, ducking and anti-feedback.
3. `media-karaoke-themes`: local video/audio player, educational bilingual view, karaoke timestamps, music mode, themes and SRT/VTT export.

Each follow-on plan inherits the constraints and acceptance gates from `docs/superpowers/specs/2026-08-18-milyvoice-1.0.5-master-spec.md`.
