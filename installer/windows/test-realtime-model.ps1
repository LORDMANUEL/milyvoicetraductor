[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$env:HF_HUB_DISABLE_TELEMETRY = '1'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$FixtureRoot = Join-Path $Root '.build\realtime-model-smoke'
$AppRoot = Join-Path $FixtureRoot 'MilyVoiceTraductor'
$RuntimeRoot = Join-Path $AppRoot 'runtime\python'
$EngineApp = Join-Path $AppRoot 'engine\app'
$ConfigRoot = Join-Path $AppRoot 'config'
$CacheRoot = Join-Path $AppRoot 'cache'
$ModelsRoot = Join-Path $AppRoot 'models'
$RuntimeZip = Join-Path $Root 'dist\runtime\milyvoice-python-runtime.zip'
$PerformanceRoot = Join-Path $Root 'dist\performance'
$ReportPath = Join-Path $PerformanceRoot 'MilyVoiceTraductor-2.0.0-MegaBench.json'
$BenchmarkWave = Join-Path $FixtureRoot 'benchmark-en.wav'

Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $RuntimeRoot,$EngineApp,$ConfigRoot,$CacheRoot,$ModelsRoot,$PerformanceRoot | Out-Null
Remove-Item $ReportPath -Force -ErrorAction SilentlyContinue

try {
    Expand-Archive -Path $RuntimeZip -DestinationPath $RuntimeRoot -Force
    Copy-Item (Join-Path $Root 'services\ai\*') $EngineApp -Recurse -Force

    $Python = Join-Path $RuntimeRoot 'python.exe'
    $EngineMain = Join-Path $EngineApp 'main.py'
    if (-not (Test-Path $Python -PathType Leaf)) { throw 'El runtime privado no contiene python.exe.' }
    if (-not (Test-Path $EngineMain -PathType Leaf)) { throw 'El fixture no contiene main.py.' }

    Write-Host '[MEGABENCH] Instalando pack real realtime-m2m100...'
    & $Python $EngineMain models `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot `
        install realtime-m2m100 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo descargar/convertir realtime-m2m100.' }

    & $Python $EngineMain models `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot `
        verify realtime-m2m100 1.0.0 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'El pack realtime-m2m100 no pasó verify.' }

    Write-Host '[MEGABENCH] Generando fixture de voz inglesa local con Windows SAPI...'
    try {
        Add-Type -AssemblyName System.Speech
        $synth = [System.Speech.Synthesis.SpeechSynthesizer]::new()
        try {
            $englishVoice = $synth.GetInstalledVoices() |
                Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'en-*' } |
                Select-Object -First 1
            if ($englishVoice) { $synth.SelectVoice($englishVoice.VoiceInfo.Name) }
            $synth.Rate = 0
            $synth.SetOutputToWaveFile($BenchmarkWave)
            $synth.Speak('Good morning. The meeting starts at nine. Please confirm order one zero three eight and do not cancel it. We are testing real time translation performance.')
        } finally {
            $synth.Dispose()
        }
    } catch {
        throw "No se pudo generar el fixture de voz para MegaBench: $($_.Exception.Message)"
    }
    if (-not (Test-Path $BenchmarkWave -PathType Leaf)) { throw 'MegaBench no generó el WAV de referencia.' }

    $Probe = Join-Path $FixtureRoot 'probe_realtime.py'
    @'
from pathlib import Path
import json
import math
import platform
import sys
import time
import wave

import numpy as np

engine_app = Path(sys.argv[1])
models_root = Path(sys.argv[2])
audio_path = Path(sys.argv[3])
report_path = Path(sys.argv[4])
sys.path.insert(0, str(engine_app))

from mily_ai.benchmarking import performance_gate, percentile, summarize_latencies
from mily_ai.models import ModelCatalog
from mily_ai.providers import FasterWhisperAsr, M2M100CTranslate2Translator


def load_wav_mono_16k(path: Path):
    with wave.open(str(path), 'rb') as source:
        channels = source.getnchannels()
        width = source.getsampwidth()
        rate = source.getframerate()
        frames = source.getnframes()
        raw = source.readframes(frames)
    if width == 1:
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif width == 2:
        samples = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
    elif width == 4:
        samples = np.frombuffer(raw, dtype='<i4').astype(np.float32) / 2147483648.0
    else:
        raise SystemExit(f'WAV width no soportado: {width}')
    if channels > 1:
        usable = samples[: samples.size - (samples.size % channels)]
        samples = usable.reshape(-1, channels).mean(axis=1)
    if rate != 16000:
        target_length = max(1, round(samples.size * 16000 / rate))
        source_positions = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
        target_positions = np.linspace(0.0, 1.0, num=target_length, endpoint=False)
        samples = np.interp(target_positions, source_positions, samples).astype(np.float32)
    return samples.astype(np.float32, copy=False), len(samples) / 16000.0


pack = ModelCatalog(models_root).active_pack()
if pack is None or pack.id != 'realtime-m2m100':
    raise SystemExit('El pack realtime no quedó activo')

samples, audio_seconds = load_wav_mono_16k(audio_path)
if audio_seconds < 2.0:
    raise SystemExit(f'Fixture de voz demasiado corto: {audio_seconds:.2f}s')

asr = FasterWhisperAsr(pack.path / 'components' / 'asr', 'cpu')
asr.warm_up('en')
asr_latencies = []
asr_rtfs = []
asr_text = ''
for _ in range(5):
    started = time.perf_counter()
    segments = asr.transcribe(samples, 'en')
    elapsed = time.perf_counter() - started
    text = ' '.join(segment.text for segment in segments if segment.text).strip()
    if not text:
        raise SystemExit('Whisper Small no transcribió el fixture de voz real')
    asr_text = text
    asr_latencies.append(elapsed * 1000.0)
    asr_rtfs.append(elapsed / audio_seconds)

translator = M2M100CTranslate2Translator(pack.path / 'components' / 'translation', 'cpu')
translator.warm_up()

en_phrases = [
    'Good morning, the meeting starts at nine.',
    'Please confirm order 1038 and do not cancel it.',
    'The customer needs the invoice before five thirty.',
    'We need to review the network issue after lunch.',
    'The microphone is connected and the audio is clear.',
    'Please send the technical report tomorrow morning.',
]
zh_phrases = [
    '你好，会议九点开始。',
    '请确认订单1038，不要取消。',
    '客户需要在五点半之前收到发票。',
    '午饭后我们需要检查网络问题。',
    '麦克风已连接，声音很清楚。',
    '请明天早上发送技术报告。',
]


def benchmark_translation(phrases, language, rounds=4):
    latencies = []
    outputs = []
    for _ in range(rounds):
        for phrase in phrases:
            started = time.perf_counter()
            translated = translator.translate(phrase, language)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            if not translated.strip() or translated.strip().casefold() == phrase.strip().casefold():
                raise SystemExit(f'Traducción {language}→ES inválida: {translated!r}')
            latencies.append(elapsed_ms)
            outputs.append(translated)
    return latencies, outputs


en_latencies, en_outputs = benchmark_translation(en_phrases, 'en')
zh_latencies, zh_outputs = benchmark_translation(zh_phrases, 'zh')
asr_summary = summarize_latencies(asr_latencies)
en_summary = summarize_latencies(en_latencies)
zh_summary = summarize_latencies(zh_latencies)
asr_rtf_p50 = percentile(asr_rtfs, 50.0)
asr_rtf_p95 = percentile(asr_rtfs, 95.0)
mt_p95 = max(float(en_summary['p95Ms']), float(zh_summary['p95Ms']))

# Límites deliberadamente de regresión CI, no del objetivo físico Legacy Haswell.
gate = performance_gate(
    asr_rtf_p95=asr_rtf_p95,
    mt_p95_ms=mt_p95,
    max_asr_rtf_p95=2.50,
    max_mt_p95_ms=2500.0,
)

report = {
    'schemaVersion': 1,
    'productVersion': '2.0.0',
    'modelPack': f'{pack.id}@{pack.version}',
    'mode': 'github-windows-regression-gate',
    'physicalLegacyHaswellGateExecuted': False,
    'environment': {
        'platform': platform.platform(),
        'processor': platform.processor(),
        'python': platform.python_version(),
    },
    'fixture': {
        'audioSeconds': round(audio_seconds, 3),
        'sampleRate': 16000,
        'asrIterations': len(asr_latencies),
        'mtIterationsPerDirection': len(en_latencies),
    },
    'asr': {
        **asr_summary,
        'rtfP50': round(asr_rtf_p50, 4),
        'rtfP95': round(asr_rtf_p95, 4),
        'recognizedPreview': asr_text[:240],
    },
    'translation': {
        'enEs': {**en_summary, 'preview': en_outputs[-1][:240]},
        'zhEs': {**zh_summary, 'preview': zh_outputs[-1][:240]},
    },
    'estimatedEndToEndP95Ms': round(float(asr_summary['p95Ms']) + mt_p95, 3),
    'gate': gate,
    'notes': [
        'Este gate mide regresiones en el runner Windows de GitHub.',
        'No equivale al benchmark físico obligatorio del perfil Legacy sobre Intel Core i3 Haswell.',
        'EN→ES y ZH→ES son smoke reales prioritarios de esta candidata.',
    ],
}
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

print('REALTIME_MODEL_LOAD_OK')
print('ASR_TEXT', asr_text)
print('ASR_P50_MS', asr_summary['p50Ms'])
print('ASR_P95_MS', asr_summary['p95Ms'])
print('ASR_RTF_P50', round(asr_rtf_p50, 4))
print('ASR_RTF_P95', round(asr_rtf_p95, 4))
print('EN_ES_P50_MS', en_summary['p50Ms'])
print('EN_ES_P95_MS', en_summary['p95Ms'])
print('ZH_ES_P50_MS', zh_summary['p50Ms'])
print('ZH_ES_P95_MS', zh_summary['p95Ms'])
print('MEGABENCH_REPORT', report_path)
if not gate['passed']:
    raise SystemExit('MEGABENCH PERFORMANCE GATE FAILED: ' + ','.join(gate['failures']))
print('MEGABENCH_2_0_OK')
'@ | Set-Content -Path $Probe -Encoding UTF8

    & $Python $Probe $EngineApp $ModelsRoot $BenchmarkWave $ReportPath
    if ($LASTEXITCODE -ne 0) { throw 'MegaBench 2.0 falló al ejecutar el pack real o sus límites de rendimiento.' }
    if (-not (Test-Path $ReportPath -PathType Leaf)) { throw 'MegaBench no produjo su reporte JSON.' }

    Write-Host "MEGABENCH 2.0 OK: $ReportPath" -ForegroundColor Green
}
finally {
    Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
}
