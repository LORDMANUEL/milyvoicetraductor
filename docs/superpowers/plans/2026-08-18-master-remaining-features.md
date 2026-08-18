# MilyVoiceTraductor MASTER Remaining Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completar los requisitos pendientes de `MASTER.md` sin degradar privacidad ni tiempo real: loopback WASAPI nativo, identificación local de hablantes, karaoke con timestamps, TTS con anti-feedback sin perder audio y exportación bilingüe/VTT.

**Architecture:** El motor Python seguirá siendo el bus de audio/IA. Las fuentes externas envían PCM por WebSocket; `system_loopback` será capturado dentro del motor en Windows mediante WASAPI/PyAudioWPatch y alimentará la misma cola. Diarización ligera, timestamps y anti-feedback vivirán en módulos independientes del pipeline; Desktop solo consume eventos y controla modos/voz. Las sesiones conservarán un esquema ampliado compatible hacia atrás.

**Tech Stack:** Python 3.13, FastAPI/WebSocket, NumPy, faster-whisper/CTranslate2, PyAudioWPatch 0.2.12.8 solo Windows, Svelte/TypeScript, Rust/Tauri.

**Spec:** `docs/superpowers/specs/2026-08-18-milyvoice-1.0.5-master-spec.md`

## Global Constraints

- Versión visible y empaquetada: `1.0.5`.
- Todo audio/transcripción/traducción/TTS permanece local salvo descarga inicial de modelos/dependencias de build.
- No mostrar CMD/PowerShell/Python al usuario.
- No perder utterances finales para reducir latencia.
- CPU sin GPU debe seguir siendo ruta de primera clase.
- `main` no se modifica hasta que `pruebas` supere gates completos.
- TDD: prueba roja -> implementación mínima -> verde -> commit.

---

### Task 1: Version gate y exportaciones completas

**Files:**
- Modify: `scripts/test_release_version.py`
- Modify: `services/ai/pyproject.toml`
- Modify: `services/ai/mily_ai/sessions.py`
- Modify: `services/ai/tests/test_sessions.py`
- Modify: `crates/mily-sessions/src/lib.rs`
- Modify: `apps/desktop/src/pages/Sessions.svelte`

**Interfaces:**
- `TranscriptWord(start: float, end: float, text: str)`.
- `TranscriptSegment(..., speaker_id: str | None = None, words: tuple[TranscriptWord, ...] = ())`.
- `SessionResult` expone `txt_path`, `srt_path`, `srt_bilingual_path`, `vtt_path`.
- Export formats Desktop/Rust: `txt | srt | srt-bilingual | vtt`.

- [ ] **Step 1: Añadir pruebas rojas de exportación y gate de versión**

```python
recorder.add(TranscriptSegment(
    0.0, 1.5, "hello world", "hola mundo",
    speaker_id="speaker-a",
    words=(TranscriptWord(0.0, 0.6, "hello"), TranscriptWord(0.6, 1.5, "world")),
))
result = recorder.finish()
assert "hello world" in result.txt_path.read_text(encoding="utf-8")
assert result.srt_bilingual_path.exists()
assert result.vtt_path.read_text(encoding="utf-8").startswith("WEBVTT")
```

- [ ] **Step 2: Verificar rojo**

Run: `PYTHONPATH=services/ai python -m unittest services.ai.tests.test_sessions -v`
Expected: FAIL porque `TranscriptWord`, SRT bilingüe y VTT todavía no existen.

- [ ] **Step 3: Implementar exportadores y gate `pyproject.toml`**

Usar `tomllib` en `scripts/test_release_version.py` para exigir `project.version == "1.0.5"`; cambiar `services/ai/pyproject.toml` a `1.0.5`. Mantener `translation.srt` como español compatible y añadir `translation-bilingual.srt` + `translation.vtt`.

- [ ] **Step 4: Verificar verde Python/Rust/frontend**

Run: `PYTHONPATH=services/ai python -m unittest services.ai.tests.test_sessions -v`
Run: `cargo test -p mily-sessions`
Run: `npm run --prefix apps/desktop typecheck`

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: add bilingual session exports and strict version gate"
```

### Task 2: Karaoke y timestamps de palabra

**Files:**
- Modify: `services/ai/mily_ai/protocol.py`
- Modify: `services/ai/mily_ai/providers.py`
- Modify: `services/ai/mily_ai/pipeline.py`
- Modify: `services/ai/mily_ai/server.py`
- Modify: `services/ai/tests/test_protocol.py`
- Modify: `services/ai/tests/test_pipeline_streaming.py`
- Modify: `apps/desktop/src/types.ts`
- Modify: `apps/desktop/src/lib/realtime.ts`
- Modify: `apps/desktop/src/pages/LiveTranslation.svelte`

**Interfaces:**
- `client.hello.sessionMode`: `meeting | education | karaoke | compact`.
- `AsrWord(start, end, text)` y `RealtimeEvent.words`.
- `FasterWhisperAsr(..., word_timestamps: bool)`.

- [ ] **Step 1: Prueba roja del protocolo y palabras**

```python
msg = ClientMessage.parse(json.dumps({
  "protocol": 1, "type": "client.hello", "sourceLanguage": "en",
  "targetLanguage": "es", "sessionMode": "karaoke"
}))
assert msg.session_mode == "karaoke"
```

- [ ] **Step 2: Verificar rojo**

Run: `PYTHONPATH=services/ai python -m unittest services.ai.tests.test_protocol services.ai.tests.test_pipeline_streaming -v`
Expected: FAIL por ausencia de `session_mode`/`words`.

- [ ] **Step 3: Implementar modo karaoke**

Karaoke activa `word_timestamps=True`; conversación mantiene `False`. Convertir tiempos de palabra del frame Whisper a tiempo absoluto de sesión. El servidor serializa `words` solo cuando existen. `music_mode` usa ventana/contexto más largo y VAD menos agresivo.

- [ ] **Step 4: Renderizar karaoke real**

Desktop mantiene reloj de sesión y para `media_file` lo relaciona con `HTMLMediaElement.currentTime`; cada palabra se renderiza como `<span>` y recibe clase activa cuando `start <= clock < end`. Bajo `pressure/overloaded`, degradar a frase completa.

- [ ] **Step 5: Verificar y commit**

Run: `python -m unittest discover -s services/ai/tests -v`
Run: `npm run --prefix apps/desktop typecheck && npm run --prefix apps/desktop test`
Commit: `feat: add timed karaoke word events`

### Task 3: Speaker A/B/C con clustering local

**Files:**
- Create: `services/ai/mily_ai/speakers.py`
- Create: `services/ai/tests/test_speakers.py`
- Modify: `services/ai/mily_ai/pipeline.py`
- Modify: `services/ai/mily_ai/protocol.py`
- Modify: `services/ai/mily_ai/server.py`
- Modify: `services/ai/mily_ai/sessions.py`
- Modify: `apps/desktop/src/types.ts`
- Modify: `apps/desktop/src/lib/realtime.ts`
- Modify: `apps/desktop/src/pages/LiveTranslation.svelte`

**Interfaces:**
- `SpeakerClusterer.assign(samples, *, update: bool) -> str` devuelve `speaker-a`, `speaker-b`, ...
- `speaker.focus` controla `all | dominant | fixed` y speaker opcional.
- Eventos de pipeline incluyen `speakerId`.

- [ ] **Step 1: Prueba roja del clusterer**

Crear señales sintéticas con perfiles espectrales distintos; la misma firma debe conservar ID y firmas separadas deben producir IDs diferentes cuando superen el umbral.

- [ ] **Step 2: Verificar rojo**

Run: `PYTHONPATH=services/ai python -m unittest services.ai.tests.test_speakers -v`
Expected: FAIL porque `mily_ai.speakers` no existe.

- [ ] **Step 3: Implementar embedding acústico ligero + clustering online**

Usar NumPy: normalización, ventanas, log-energía por bandas, centroid/flatness/ZCR, normalización L2 y similitud coseno. Máximo 8 clusters; centroides se actualizan solo en finales para estabilidad.

- [ ] **Step 4: Integrar foco y persistencia**

Asignar speaker antes de ASR cuando sea posible. En `fixed`, no enviar a ASR ventanas de otro speaker; en `dominant`, priorizar el cluster con más finales. Persistir `speakerId` por segmento.

- [ ] **Step 5: UI y voz por speaker**

Desktop muestra Hablante A/B/C con color estable, permite renombrar y seleccionar `Todos | Dominante | Fijado`; el mapa local de voces TTS se guarda por `speakerId` durante la sesión.

- [ ] **Step 6: Verificar y commit**

Run Python + frontend tests. Commit: `feat: add local speaker grouping and focus modes`.

### Task 4: TTS anti-feedback sin cortar captura

**Files:**
- Create: `services/ai/mily_ai/echo_guard.py`
- Create: `services/ai/tests/test_echo_guard.py`
- Modify: `services/ai/mily_ai/protocol.py`
- Modify: `services/ai/mily_ai/pipeline.py`
- Modify: `services/ai/mily_ai/server.py`
- Modify: `apps/desktop/src/lib/realtime.ts`
- Modify: `apps/desktop/src/pages/LiveTranslation.svelte`
- Modify: `apps/extension/background.js`
- Modify: `apps/extension/offscreen.js`

**Interfaces:**
- Control frames: `tts.started { text, speakerId? }`, `tts.finished`.
- `EchoGuard.register(text)`, `EchoGuard.matches(text)`.

- [ ] **Step 1: Prueba roja**

Registrar `"hola mundo"`; `matches("hola mundo")` y una variante con puntuación deben ser true, una frase inglesa distinta false.

- [ ] **Step 2: Implementar guard textual temporal**

Normalizar Unicode/case/puntuación y usar similitud por tokens/secuencia con TTL corto. No descartar audio: solo suprimir hipótesis claramente equivalentes al TTS reciente.

- [ ] **Step 3: Quitar `outputSuppressed` como mecanismo normal**

Desktop mantiene captura durante TTS, manda `tts.started/finished`; para media usa ducking de ganancia. Micrófono conserva AEC del navegador. `system_loopback` se protege por EchoGuard.

- [ ] **Step 4: Verificar y commit**

Run Python/frontend/extension guards. Commit: `fix: prevent TTS feedback without dropping incoming audio`.

### Task 5: WASAPI system_loopback real y gates de release

**Files:**
- Create: `services/ai/mily_ai/system_loopback.py`
- Create: `services/ai/tests/test_system_loopback.py`
- Modify: `services/ai/pyproject.toml`
- Modify: `services/ai/requirements.runtime.txt`
- Modify: `installer/windows/build-python-runtime.ps1`
- Modify: `services/ai/mily_ai/protocol.py`
- Modify: `services/ai/mily_ai/server.py`
- Modify: `apps/desktop/src/lib/realtime.ts`
- Modify: `apps/desktop/src/pages/LiveTranslation.svelte`
- Modify: `.github/workflows/ci.yml`
- Modify: `MASTER.md`

**Interfaces:**
- `client.hello.sourceMode`: `browser_tab | microphone | media_file | system_loopback`.
- `WasapiLoopbackSource.open_default()`, `read_chunk() -> list[float]`, `close()`.

- [ ] **Step 1: Prueba roja con backend inyectable**

Mockear solo el backend hardware; validar selección del loopback predeterminado, mezcla a mono y resample a 16 kHz sin depender de hardware CI.

- [ ] **Step 2: Implementar WASAPI con PyAudioWPatch 0.2.12.8**

Solo en Windows. Abrir `get_default_wasapi_loopback()`, usar formato float32, 100 ms por chunk, mezclar canales y remuestrear con NumPy. Errores públicos: `LOOPBACK_UNAVAILABLE`, `LOOPBACK_DEVICE`, `LOOPBACK_CAPTURE`.

- [ ] **Step 3: Integrar motor/Desktop**

Cuando `sourceMode=system_loopback`, el motor alimenta `audio_queue` internamente; Desktop deja `getDisplayMedia` como fallback manual únicamente si el backend nativo no está disponible.

- [ ] **Step 4: Endurecer runtime**

Agregar `PyAudioWPatch==0.2.12.8; sys_platform == "win32"` al runtime y hacer que `build-python-runtime.ps1` verifique `import pyaudiowpatch` en Windows.

- [ ] **Step 5: Gate real pre-merge**

Configurar CI para ejecutar `test-realtime-model.ps1` en `main` y también en PR no-draft hacia `main`; añadir test de loopback en runner Windows cuando hardware lo permita y mantener unit test determinista siempre.

- [ ] **Step 6: Verificación integral**

Python unit tests + compileall, frontend typecheck/tests/build, Rust fmt/tests/clippy Linux+Windows, runtime privado, GUI subsystem, NSIS real, extensión, SHA256.

- [ ] **Step 7: Actualizar MASTER y commit**

Marcar únicamente componentes realmente implementados; no marcar release estable hasta prueba real y merge final.
