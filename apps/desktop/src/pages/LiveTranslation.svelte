<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { desktopApi } from '../lib/api';
  import { DesktopAudioCapture } from '../lib/realtime';
  import type { AppStatus, RealtimeEvent, RealtimeWord, SpeakerFocusMode } from '../types';

  type SourceMode = 'browser' | 'microphone' | 'system' | 'media';
  type VisualMode = 'meeting' | 'education' | 'karaoke' | 'compact';
  type VisualTheme = 'mily' | 'cinema' | 'class' | 'contrast' | 'neon';

  interface TranscriptRow { start: number; original: string; translation: string; speakerId: string | null; }

  let appStatus: AppStatus | null = null;
  let source: SourceMode = 'microphone';
  let sourceLanguage: 'auto' | 'en' | 'zh' = 'auto';
  let persistTranscript = false;
  let visualMode: VisualMode = 'meeting';
  let visualTheme: VisualTheme = 'mily';
  let active = false;
  let busy = false;
  let message = 'Seleccione una fuente y pulse Iniciar.';
  let error = '';
  let currentOriginal = '';
  let currentTranslation = '';
  let currentWords: RealtimeWord[] = [];
  let currentSpeakerId: string | null = null;
  let knownSpeakers: string[] = [];
  let speakerDetection = false;
  let speakerFocusMode: SpeakerFocusMode = 'all';
  let fixedSpeakerId = '';
  let speakerNames: Record<string, string> = {};
  let speakerVoiceNames: Record<string, string> = {};
  let karaokeClock = 0;
  let sessionStartedAt = 0;
  let frameRequest = 0;
  let audioRms = 0;
  let silentMs = 0;
  let pressure: 'healthy' | 'pressure' | 'overloaded' = 'healthy';
  let asrP50 = 0;
  let translationP50 = 0;
  let realTimeFactor = 0;
  let transcript: TranscriptRow[] = [];
  let mediaUrl = '';
  let mediaName = '';
  let mediaIsVideo = false;
  let videoElement: HTMLVideoElement;
  let audioElement: HTMLAudioElement;
  let ttsEnabled = false;
  let ttsVoiceName = '';
  let ttsVoices: SpeechSynthesisVoice[] = [];
  let ttsGeneration = 0;
  let capture: DesktopAudioCapture;

  function activeMediaElement(): HTMLMediaElement | null {
    if (!mediaUrl) return null;
    return mediaIsVideo ? videoElement : audioElement;
  }

  function tickKaraoke() {
    if (source === 'media') karaokeClock = activeMediaElement()?.currentTime || 0;
    else if (sessionStartedAt > 0) karaokeClock = Math.max(0, performance.now() / 1000 - sessionStartedAt);
    frameRequest = window.requestAnimationFrame(tickKaraoke);
  }

  function isActiveWord(word: RealtimeWord): boolean {
    return pressure === 'healthy' && karaokeClock >= word.start && karaokeClock < word.end;
  }

  function speakerLabel(id: string | null): string {
    if (!id) return '';
    if (speakerNames[id]?.trim()) return speakerNames[id].trim();
    const suffix = id.replace(/^speaker-/, '').toUpperCase();
    return `Hablante ${suffix}`;
  }

  function speakerClass(id: string | null): string {
    if (!id) return 'speaker-none';
    const index = Math.max(0, knownSpeakers.indexOf(id));
    return `speaker-${index % 6}`;
  }

  function rememberSpeaker(id: string | null | undefined) {
    if (!id) return;
    currentSpeakerId = id;
    if (!knownSpeakers.includes(id)) {
      knownSpeakers = [...knownSpeakers, id];
      if (!fixedSpeakerId) fixedSpeakerId = id;
    }
  }

  function refreshVoices() {
    if (!('speechSynthesis' in window)) return;
    const voices = window.speechSynthesis.getVoices();
    const spanish = voices.filter((voice) => voice.lang.toLowerCase().startsWith('es'));
    const localSpanish = spanish.filter((voice) => voice.localService !== false);
    ttsVoices = localSpanish.length ? localSpanish : spanish;
    if (!ttsVoiceName && ttsVoices.length) ttsVoiceName = ttsVoices[0].name;
  }

  function selectedVoiceForSpeaker(speakerId: string | null): SpeechSynthesisVoice | undefined {
    const configured = speakerId ? speakerVoiceNames[speakerId] : '';
    const name = configured || ttsVoiceName;
    return ttsVoices.find((voice) => voice.name === name);
  }

  function releaseTtsGuard(generation: number, speakerId: string | null) {
    if (generation !== ttsGeneration) return;
    capture.notifyTtsFinished(speakerId);
    window.setTimeout(() => {
      if (generation !== ttsGeneration) return;
      capture.setPlaybackGain(1);
    }, 220);
  }

  function speakSpanish(text: string, speakerId: string | null) {
    if (!ttsEnabled || !text || !('speechSynthesis' in window)) return;
    ttsGeneration += 1;
    const generation = ttsGeneration;
    window.speechSynthesis.cancel();
    capture.notifyTtsStarted(text, speakerId);
    capture.setPlaybackGain(0.25);
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'es-ES';
    const selected = selectedVoiceForSpeaker(speakerId);
    if (selected) utterance.voice = selected;
    utterance.rate = 1.08;
    utterance.onend = () => releaseTtsGuard(generation, speakerId);
    utterance.onerror = () => releaseTtsGuard(generation, speakerId);
    window.speechSynthesis.speak(utterance);
  }

  function acceptWords(event: RealtimeEvent) {
    if (event.words?.length) currentWords = event.words;
  }

  function updateSpeakerFocus() {
    if (speakerFocusMode === 'fixed' && !fixedSpeakerId) return;
    if (active) capture.setSpeakerFocus(speakerFocusMode, speakerFocusMode === 'fixed' ? fixedSpeakerId : null);
  }

  function handleRealtimeEvent(event: RealtimeEvent) {
    rememberSpeaker(event.speakerId);
    if (event.type === 'speaker.changed') { rememberSpeaker(event.speakerId); return; }
    if (event.type === 'engine.loading') { message = 'Precalentando Whisper y M2M100…'; return; }
    if (event.type === 'session.started') {
      sessionStartedAt = performance.now() / 1000;
      karaokeClock = 0;
      message = event.sourceMode === 'system_loopback' ? 'WASAPI activo · esperando audio del sistema.' : 'Sesión lista · esperando audio.';
      return;
    }
    if (event.type === 'audio.level') {
      audioRms = Number(event.rms || 0); silentMs = Number(event.silentMs || 0);
      if (event.speech) message = 'Audio detectado · escuchando…';
      else if (silentMs >= 3000) message = 'No se detecta audio en esta fuente.';
      else message = 'Silencio · esperando voz…';
      return;
    }
    if (event.type === 'pipeline.metrics') {
      pressure = event.pressure || 'healthy';
      asrP50 = Number(event.asrP50Ms || 0); translationP50 = Number(event.translationP50Ms || 0);
      realTimeFactor = Number(event.realTimeFactor || 0);
      if (pressure === 'overloaded') message = 'CPU al límite · karaoke por frase y prioridad a finales.';
      else if (pressure === 'pressure') message = 'CPU ocupada · karaoke por frase y menos parciales.';
      return;
    }
    if (event.type === 'transcription.partial' || event.type === 'transcription.final') {
      currentOriginal = event.original || currentOriginal;
      acceptWords(event);
      if (event.type === 'transcription.partial') message = 'Transcribiendo…';
      return;
    }
    if (event.type === 'translation.partial') {
      currentOriginal = event.original || currentOriginal; currentTranslation = event.translation || currentTranslation;
      acceptWords(event);
      message = 'Traduciendo frase…'; return;
    }
    if (event.type === 'translation.final') {
      currentOriginal = event.original || currentOriginal; currentTranslation = event.translation || '';
      acceptWords(event);
      const speakerId = event.speakerId || currentSpeakerId;
      rememberSpeaker(speakerId);
      transcript = [...transcript, { start: Number(event.start || 0), original: currentOriginal, translation: currentTranslation, speakerId }].slice(-80);
      message = 'Traducción al día.'; speakSpanish(currentTranslation, speakerId); return;
    }
    if (event.type === 'engine.error') { error = event.message || 'El motor local reportó un error.'; message = 'Error del motor.'; }
  }

  async function start() {
    error = '';
    if (source === 'browser') {
      message = appStatus?.extensionConnected
        ? 'Abra la extensión en Chrome/Edge y pulse Iniciar traducción sobre la pestaña deseada.'
        : 'Abra Chrome/Edge, instale/active la extensión y vuelva a intentar.';
      return;
    }
    if (source === 'media' && !mediaUrl) { error = 'Seleccione primero un archivo de video o audio.'; return; }
    if (speakerFocusMode === 'fixed' && !fixedSpeakerId) { error = 'Seleccione primero el hablante que desea fijar.'; return; }
    busy = true; message = 'Preparando motor y modelos locales…';
    const selectedSpeaker = speakerFocusMode === 'fixed' ? fixedSpeakerId : null;
    try {
      if (source === 'microphone') await capture.startMicrophone(sourceLanguage, persistTranscript, visualMode, speakerDetection, speakerFocusMode, selectedSpeaker);
      else if (source === 'system') await capture.startSystemAudio(sourceLanguage, persistTranscript, visualMode, speakerDetection, speakerFocusMode, selectedSpeaker);
      else {
        const element = activeMediaElement();
        if (!element) throw new Error('El archivo multimedia todavía no está listo.');
        await capture.startMediaElement(element, sourceLanguage, persistTranscript, visualMode, speakerDetection, speakerFocusMode, selectedSpeaker);
        message = 'Motor listo. Pulse Play en el reproductor para comenzar.';
      }
      active = true;
    } catch (caught) { error = caught instanceof Error ? caught.message : 'No se pudo iniciar la captura.'; active = false; }
    finally { busy = false; }
  }

  async function stop() {
    busy = true;
    try {
      ttsGeneration += 1;
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
      capture.notifyTtsFinished(currentSpeakerId);
      capture.setPlaybackGain(1);
      await capture.stop(); active = false; sessionStartedAt = 0; message = 'Traducción detenida.';
    } finally { busy = false; }
  }

  async function toggle() { if (active) await stop(); else await start(); }

  function chooseSource(next: SourceMode) {
    if (active || busy) return;
    source = next; error = '';
    message = next === 'browser' ? 'Use la extensión en cualquier pestaña web capturable.'
      : next === 'media' ? 'Seleccione un archivo local y luego inicie el traductor.'
      : 'Pulse Iniciar para preparar esta fuente.';
  }

  function chooseMedia(event: Event) {
    const input = event.currentTarget as HTMLInputElement; const file = input.files?.[0];
    if (!file) return;
    if (mediaUrl) URL.revokeObjectURL(mediaUrl);
    mediaUrl = URL.createObjectURL(file); mediaName = file.name; mediaIsVideo = file.type.startsWith('video/');
    currentOriginal = ''; currentTranslation = ''; currentWords = []; transcript = [];
  }

  function formatTime(seconds: number) {
    const minutes = Math.floor(seconds / 60); const rest = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${minutes}:${rest}`;
  }

  onMount(async () => {
    capture = new DesktopAudioCapture(handleRealtimeEvent);
    appStatus = await desktopApi.getAppStatus();
    const config = await desktopApi.getConfig(); sourceLanguage = config.sourceLanguage; persistTranscript = config.persistTranscripts;
    refreshVoices();
    frameRequest = window.requestAnimationFrame(tickKaraoke);
    if ('speechSynthesis' in window) window.speechSynthesis.onvoiceschanged = refreshVoices;
  });

  onDestroy(() => {
    ttsGeneration += 1;
    window.cancelAnimationFrame(frameRequest);
    if ('speechSynthesis' in window) { window.speechSynthesis.cancel(); window.speechSynthesis.onvoiceschanged = null; }
    capture?.stop().catch(() => undefined);
    if (mediaUrl) URL.revokeObjectURL(mediaUrl);
  });
</script>

<section class="page-stack live-page">
  <header class="page-header">
    <div><p class="eyebrow">TRADUCCIÓN · LOCAL · {appStatus?.version ?? '2.0.2'}</p><h1>Escuche, traduzca y enseñe en tiempo real</h1><p>Reuniones, micrófono, audio del sistema, videos, cursos y canciones sin enviar audio a la nube.</p></div>
    <span class:ok={active} class:warning={!active} class="status-badge"><span class="status-dot"></span>{active ? 'Capturando' : 'En espera'}</span>
  </header>

  <div class="source-grid" aria-label="Fuentes de audio">
    <button class:active={source === 'browser'} on:click={() => chooseSource('browser')} disabled={active || busy}><span>WEB</span><strong>Navegador</strong><small>YouTube, Meet, cursos, radio web</small></button>
    <button class:active={source === 'microphone'} on:click={() => chooseSource('microphone')} disabled={active || busy}><span>MIC</span><strong>Micrófono</strong><small>Conversación, clase o práctica oral</small></button>
    <button class:active={source === 'system'} on:click={() => chooseSource('system')} disabled={active || busy}><span>PC</span><strong>Audio del sistema</strong><small>WASAPI nativo con fallback protegido</small></button>
    <button class:active={source === 'media'} on:click={() => chooseSource('media')} disabled={active || busy}><span>AV</span><strong>Video / Audio</strong><small>MP4, WebM, MP3, WAV, M4A compatibles</small></button>
  </div>

  <div class="workspace-grid">
    <article class="panel-card controls-panel">
      <div class="panel-title"><h3>Sesión</h3><span class="pill ok">127.0.0.1</span></div>
      <div class="control-grid">
        <label>Idioma de origen<select bind:value={sourceLanguage} disabled={active || busy}><option value="auto">Automático</option><option value="en">Inglés</option><option value="zh">Chino</option></select></label>
        <label>Vista<select bind:value={visualMode} disabled={active || busy}><option value="meeting">Reunión</option><option value="education">Educativo</option><option value="karaoke">Karaoke</option><option value="compact">Compacto</option></select></label>
        <label>Tema<select bind:value={visualTheme}><option value="mily">Mily azul</option><option value="cinema">Oscuro cine</option><option value="class">Clase clara</option><option value="contrast">Alto contraste</option><option value="neon">Karaoke neón</option></select></label>
      </div>
      <label class="switch-line"><input type="checkbox" bind:checked={persistTranscript} disabled={active} /> Guardar transcripción local</label>
      <label class="switch-line"><input type="checkbox" bind:checked={speakerDetection} disabled={active} /> Identificar Hablante A/B/C localmente</label>
      {#if speakerDetection}
        <div class="speaker-focus-grid">
          <label>Escuchar<select bind:value={speakerFocusMode} on:change={updateSpeakerFocus}><option value="all">Todos</option><option value="dominant">Voz dominante</option><option value="fixed">Fijar hablante</option></select></label>
          {#if speakerFocusMode === 'fixed'}<label>Hablante<select bind:value={fixedSpeakerId} on:change={updateSpeakerFocus}><option value="">Seleccione…</option>{#each knownSpeakers as id}<option value={id}>{speakerLabel(id)}</option>{/each}</select></label>{/if}
        </div>
      {/if}
      <label class="switch-line"><input type="checkbox" bind:checked={ttsEnabled} /> Voz española en tiempo real</label>
      {#if ttsEnabled}<label>Voz española predeterminada<select bind:value={ttsVoiceName}>{#if ttsVoices.length === 0}<option value="">Voz predeterminada del sistema</option>{/if}{#each ttsVoices as voice}<option value={voice.name}>{voice.name} · {voice.lang}</option>{/each}</select></label>{/if}

      {#if knownSpeakers.length}
        <div class="speaker-list" aria-label="Hablantes detectados">
          {#each knownSpeakers as id}
            <div class="speaker-card {speakerClass(id)}">
              <span class="speaker-dot"></span>
              <input aria-label={`Nombre de ${speakerLabel(id)}`} value={speakerNames[id] || speakerLabel(id)} on:input={(event) => { speakerNames = { ...speakerNames, [id]: (event.currentTarget as HTMLInputElement).value }; }} />
              {#if ttsEnabled}<select aria-label={`Voz para ${speakerLabel(id)}`} value={speakerVoiceNames[id] || ''} on:change={(event) => { speakerVoiceNames = { ...speakerVoiceNames, [id]: (event.currentTarget as HTMLSelectElement).value }; }}><option value="">Voz predeterminada</option>{#each ttsVoices as voice}<option value={voice.name}>{voice.name}</option>{/each}</select>{/if}
              {#if currentSpeakerId === id}<strong>Activo</strong>{/if}
            </div>
          {/each}
        </div>
      {/if}

      {#if source === 'media'}
        <label class="file-picker">Archivo local<input type="file" accept="audio/*,video/*" on:change={chooseMedia} disabled={active} /><span>{mediaName || 'Seleccione un video o audio'}</span></label>
      {:else if source === 'browser'}
        <div class="browser-hint"><strong>{appStatus?.extensionConnected ? 'Extensión conectada' : 'Extensión no detectada todavía'}</strong><p>Abra cualquier pestaña web con audio, pulse la extensión MilyVoiceTraductor y después “Iniciar traducción”. El overlay se inyecta solo en esa pestaña.</p></div>
      {:else if source === 'system'}
        <div class="browser-hint"><strong>WASAPI loopback nativo</strong><p>MilyVoice intenta capturar directamente lo que reproduce Windows. Si WASAPI no puede abrir el dispositivo, ofrece automáticamente el selector protegido de Windows como recuperación.</p></div>
      {/if}

      <button class:stop-button={active} class="primary main-action" on:click={toggle} disabled={busy || source === 'browser'}>{busy ? 'Preparando…' : active ? 'Detener traducción' : 'Iniciar traducción'}</button>
      {#if source === 'browser'}<p class="path-hint">El inicio para Navegador se controla desde Chrome/Edge para respetar activeTab.</p>{/if}
      {#if error}<div class="inline-error">{error}</div>{/if}
    </article>

    <article class="panel-card health-panel">
      <div class="panel-title"><h3>Audio y CPU</h3><span class:danger={pressure === 'overloaded'} class:warning={pressure === 'pressure'} class:ok={pressure === 'healthy'} class="status-badge">{pressure}</span></div>
      <p class="live-message">{message}</p>
      {#if currentSpeakerId}<p class="current-speaker {speakerClass(currentSpeakerId)}"><span class="speaker-dot"></span>{speakerLabel(currentSpeakerId)}</p>{/if}
      <div class="meter"><span style:width={`${Math.min(100, audioRms * 420)}%`}></span></div>
      <div class="metric-grid"><div><small>ASR P50</small><strong>{asrP50.toFixed(0)} ms</strong></div><div><small>Traducción P50</small><strong>{translationP50.toFixed(0)} ms</strong></div><div><small>RTF</small><strong>{realTimeFactor.toFixed(2)}</strong></div><div><small>Silencio</small><strong>{(silentMs / 1000).toFixed(1)} s</strong></div></div>
      <p class="path-hint">Cuando la CPU entra en presión, se reducen parciales; las frases finales no se descartan.</p>
    </article>
  </div>

  {#if source === 'media' && mediaUrl}
    <article class="media-stage theme-{visualTheme}">
      {#if mediaIsVideo}<video bind:this={videoElement} src={mediaUrl} controls playsinline></video>{:else}<div class="audio-art">♪<span>{mediaName}</span></div><audio bind:this={audioElement} src={mediaUrl} controls></audio>{/if}
      <div class="caption-layer mode-{visualMode}">
        {#if currentSpeakerId}<em class="caption-speaker {speakerClass(currentSpeakerId)}">{speakerLabel(currentSpeakerId)}</em>{/if}
        {#if visualMode === 'meeting'}<small>{currentOriginal || 'Original…'}</small><strong>{currentTranslation || 'La traducción aparecerá aquí.'}</strong>
        {:else if visualMode === 'education'}<strong>{currentTranslation || 'Español…'}</strong><small>{currentOriginal || 'English / 中文…'}</small>
        {:else if visualMode === 'karaoke'}
          <strong>{currentTranslation || 'Traducción española…'}</strong>
          <small class="karaoke-line">
            {#if currentWords.length && pressure === 'healthy'}
              {#each currentWords as word}<span class:active-word={isActiveWord(word)}>{word.text} </span>{/each}
            {:else}{currentOriginal || 'Original sincronizado por frase…'}{/if}
          </small>
        {:else}<strong>{currentTranslation || currentOriginal || 'Esperando audio…'}</strong>{/if}
      </div>
    </article>
  {:else}
    <article class="caption-preview theme-{visualTheme} mode-{visualMode}">
      {#if currentSpeakerId}<em class="caption-speaker {speakerClass(currentSpeakerId)}">{speakerLabel(currentSpeakerId)}</em>{/if}
      {#if visualMode === 'meeting'}<small>{currentOriginal || 'Original en tiempo real…'}</small><strong>{currentTranslation || 'La traducción al español aparecerá aquí.'}</strong>
      {:else if visualMode === 'education'}<strong>{currentTranslation || 'Español…'}</strong><small>{currentOriginal || 'English / 中文…'}</small>
      {:else if visualMode === 'karaoke'}
        <strong>{currentTranslation || 'Español…'}</strong>
        <small class="karaoke-line">{#if currentWords.length && pressure === 'healthy'}{#each currentWords as word}<span class:active-word={isActiveWord(word)}>{word.text} </span>{/each}{:else}{currentOriginal || 'English / 中文…'}{/if}</small>
      {:else}<strong>{currentTranslation || currentOriginal || 'Esperando audio…'}</strong>{/if}
      <em>MILYVOICETRADUCTOR · LOCAL</em>
    </article>
  {/if}

  <article class="panel-card">
    <div class="panel-title"><h3>Transcripción de esta sesión</h3><span>{transcript.length} frases finales</span></div>
    {#if transcript.length === 0}<p class="path-hint">Los parciales se muestran arriba; aquí solo se agregan frases finales para no duplicar texto.</p>{:else}<div class="transcript-list">{#each [...transcript].reverse() as row}<div class="transcript-row"><time>{formatTime(row.start)}</time><div>{#if row.speakerId}<em class="row-speaker {speakerClass(row.speakerId)}">{speakerLabel(row.speakerId)}</em>{/if}<strong>{row.translation}</strong><small>{row.original}</small></div></div>{/each}</div>{/if}
  </article>
</section>

<style>
  .live-page { --caption-bg:#10243e; --caption-fg:#fff; --caption-muted:#a9bdd9; --caption-accent:#6fe0bd; }
  .source-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
  .source-grid button { border:1px solid var(--mily-border); background:#fff; border-radius:16px; padding:16px; text-align:left; display:grid; gap:5px; color:var(--mily-navy); }
  .source-grid button.active { border-color:#46bd98; box-shadow:0 0 0 2px rgba(0,168,120,.11); background:#f4fbf8; }
  .source-grid button > span { width:36px; height:30px; display:grid; place-items:center; border-radius:9px; background:#eaf7f2; color:var(--mily-emerald-dark); font-size:10px; font-weight:900; }
  .source-grid small { color:var(--mily-muted); line-height:1.35; }
  .workspace-grid { display:grid; grid-template-columns:1.2fr .8fr; gap:16px; }
  .controls-panel { display:grid; gap:13px; }
  .control-grid, .speaker-focus-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; }
  .speaker-focus-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
  label { display:grid; gap:6px; color:var(--mily-muted); font-size:12px; font-weight:700; }
  select, input[type='file'], .speaker-card input { border:1px solid var(--mily-border); background:#fff; color:var(--mily-navy); border-radius:10px; padding:9px; width:100%; }
  .switch-line { grid-template-columns:auto 1fr; align-items:center; justify-content:start; }
  .switch-line input { margin:0; }
  .file-picker span { color:var(--mily-navy); font-weight:600; overflow-wrap:anywhere; }
  .main-action { width:100%; padding:13px; margin-top:4px; }
  .stop-button { background:#b12b2b; }
  .inline-error { padding:11px; border-radius:10px; background:#fff0ed; color:#a12626; font-weight:650; }
  .browser-hint { padding:13px; border-radius:12px; background:#f2f7fb; border:1px solid #dbe7f2; }
  .browser-hint p { margin:5px 0 0; color:var(--mily-muted); font-size:12px; line-height:1.5; }
  .health-panel { align-content:start; }
  .live-message { min-height:42px; color:var(--mily-navy); font-weight:700; }
  .meter { height:12px; border-radius:999px; overflow:hidden; background:#e8efec; margin:12px 0 18px; }
  .meter span { display:block; height:100%; min-width:2px; border-radius:inherit; background:linear-gradient(90deg,#00a878,#2875e6); transition:width .12s linear; }
  .metric-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .metric-grid div { padding:12px; border:1px solid #e7edeb; border-radius:12px; }
  .metric-grid small { display:block; color:var(--mily-muted); margin-bottom:4px; }
  .speaker-list { display:grid; gap:8px; }
  .speaker-card { display:grid; grid-template-columns:auto minmax(130px,1fr) minmax(130px,1fr) auto; gap:8px; align-items:center; border:1px solid #e4ebe8; border-radius:12px; padding:9px; }
  .speaker-card strong { font-size:11px; }
  .speaker-dot { width:10px; height:10px; border-radius:999px; display:inline-block; background:currentColor; }
  .current-speaker { display:flex; align-items:center; gap:7px; font-weight:800; margin:0 0 8px; }
  .caption-speaker, .row-speaker { display:block; font-style:normal; font-size:11px; font-weight:900; letter-spacing:.04em; margin-bottom:4px; }
  .speaker-0 { color:#1677c8; } .speaker-1 { color:#14845b; } .speaker-2 { color:#b85c19; } .speaker-3 { color:#7a4bc2; } .speaker-4 { color:#b92f69; } .speaker-5 { color:#5f6b76; }
  .media-stage { position:relative; min-height:420px; overflow:hidden; border-radius:22px; background:#07111e; display:grid; place-items:center; box-shadow:var(--mily-shadow); }
  .media-stage video { width:100%; max-height:650px; display:block; }
  .media-stage audio { width:min(720px,90%); margin:0 auto 70px; }
  .audio-art { color:#fff; font-size:82px; display:grid; place-items:center; gap:12px; min-height:320px; }
  .audio-art span { font-size:14px; color:#a9bdd9; }
  .caption-layer, .caption-preview { color:var(--caption-fg); background:var(--caption-bg); border:1px solid var(--caption-accent); }
  .caption-layer { position:absolute; z-index:4; left:50%; bottom:32px; transform:translateX(-50%); width:min(900px,88%); border-radius:17px; padding:13px 18px; text-align:center; box-shadow:0 15px 50px rgba(0,0,0,.28); }
  .caption-preview { border-radius:20px; padding:22px; text-align:center; min-height:135px; display:grid; place-items:center; align-content:center; gap:7px; box-shadow:var(--mily-shadow); }
  .caption-layer strong, .caption-preview strong { font-size:clamp(22px,3vw,34px); line-height:1.2; }
  .caption-layer small, .caption-preview small { color:var(--caption-muted); font-size:15px; }
  .caption-preview > em:not(.caption-speaker) { color:var(--caption-accent); font-size:10px; font-style:normal; letter-spacing:.14em; font-weight:900; }
  .mode-compact small { display:none; }
  .mode-compact strong { font-size:20px; }
  .karaoke-line { border-bottom:3px solid var(--caption-accent); padding-bottom:4px; }
  .karaoke-line span { transition:color .08s linear, background .08s linear; border-radius:4px; padding:0 1px; }
  .karaoke-line .active-word { color:var(--caption-bg); background:var(--caption-accent); }
  .theme-mily { --caption-bg:rgba(16,36,62,.96); --caption-fg:#fff; --caption-muted:#a9bdd9; --caption-accent:#6fe0bd; }
  .theme-cinema { --caption-bg:rgba(3,5,8,.94); --caption-fg:#fff4d6; --caption-muted:#d3c7a7; --caption-accent:#e9b949; }
  .theme-class { --caption-bg:rgba(255,255,255,.97); --caption-fg:#10243e; --caption-muted:#45627f; --caption-accent:#008b69; }
  .theme-contrast { --caption-bg:#000; --caption-fg:#fff; --caption-muted:#fff; --caption-accent:#ffff00; }
  .theme-neon { --caption-bg:rgba(14,5,30,.96); --caption-fg:#fff; --caption-muted:#7df9ff; --caption-accent:#ff4fd8; }
  .transcript-list { display:grid; gap:8px; max-height:340px; overflow:auto; }
  .transcript-row { display:grid; grid-template-columns:52px 1fr; gap:12px; padding:10px 0; border-bottom:1px solid #edf1ef; }
  .transcript-row time { color:var(--mily-muted); font-size:12px; }
  .transcript-row strong, .transcript-row small { display:block; }
  .transcript-row small { margin-top:4px; color:var(--mily-muted); }
  @media (max-width:980px) { .source-grid { grid-template-columns:1fr 1fr; } .workspace-grid { grid-template-columns:1fr; } }
  @media (max-width:720px) { .speaker-card { grid-template-columns:auto 1fr; } .speaker-card select, .speaker-card strong { grid-column:2; } }
  @media (max-width:620px) { .source-grid, .control-grid, .speaker-focus-grid { grid-template-columns:1fr; } }
</style>