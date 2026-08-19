[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$env:HF_HUB_DISABLE_TELEMETRY = '1'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$FixtureRoot = Join-Path $Root '.build\zh-es-lite-smoke'
$AppRoot = Join-Path $FixtureRoot 'MilyVoiceTraductor'
$RuntimeRoot = Join-Path $AppRoot 'runtime\python'
$EngineApp = Join-Path $AppRoot 'engine\app'
$ConfigRoot = Join-Path $AppRoot 'config'
$CacheRoot = Join-Path $AppRoot 'cache'
$ModelsRoot = Join-Path $AppRoot 'models'
$RuntimeZip = Join-Path $Root 'dist\runtime\milyvoice-python-runtime.zip'
$ReportPath = Join-Path $Root 'dist\performance\MilyVoiceTraductor-2.0.1-ZhEsLiteBench.json'
$MandarinWave = Join-Path $FixtureRoot 'benchmark-zh.wav'
$PackVersion = '1.0.1'

Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $RuntimeRoot,$EngineApp,$ConfigRoot,$CacheRoot,$ModelsRoot,(Split-Path $ReportPath) | Out-Null
Remove-Item $ReportPath -Force -ErrorAction SilentlyContinue

try {
    Expand-Archive -Path $RuntimeZip -DestinationPath $RuntimeRoot -Force
    Copy-Item (Join-Path $Root 'services\ai\*') $EngineApp -Recurse -Force

    $Python = Join-Path $RuntimeRoot 'python.exe'
    $EngineMain = Join-Path $EngineApp 'main.py'
    if (-not (Test-Path $Python -PathType Leaf)) { throw 'El runtime privado no contiene python.exe.' }

    Write-Host '[ZH-ES-LITE] Descargando/optimizando pack Lite fijado...'
    & $Python $EngineMain models `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot `
        install lite-zh-es --download-only | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar lite-zh-es.' }

    & $Python $EngineMain models `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot `
        verify lite-zh-es $PackVersion | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'El pack ZH→ES Lite no pasó verify.' }

    & $Python $EngineMain models `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot `
        activate lite-zh-es $PackVersion | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo activar lite-zh-es.' }

    $SpeechFixture = $false
    try {
        Add-Type -AssemblyName System.Speech
        $synth = [System.Speech.Synthesis.SpeechSynthesizer]::new()
        try {
            $voice = $synth.GetInstalledVoices() |
                Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'zh-*' } |
                Select-Object -First 1
            if ($voice) {
                $synth.SelectVoice($voice.VoiceInfo.Name)
                $synth.Rate = 0
                $synth.SetOutputToWaveFile($MandarinWave)
                $synth.Speak('你好，会议九点开始。请确认订单一零三八，不要取消。')
                $SpeechFixture = Test-Path $MandarinWave -PathType Leaf
            }
        } finally {
            $synth.Dispose()
        }
    } catch {
        Write-Host "[ZH-ES-LITE] Voz SAPI mandarín no disponible: $($_.Exception.Message)"
    }

    $Probe = Join-Path $FixtureRoot 'benchmark_zh_es.py'
    @'
from pathlib import Path
import json
import os
import re
import sys
import time
import wave

import numpy as np

engine_app = Path(sys.argv[1])
models_root = Path(sys.argv[2])
report_path = Path(sys.argv[3])
wave_path = Path(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else None
sys.path.insert(0, str(engine_app))

from mily_ai.benchmarking import summarize_latencies
from mily_ai.cpu_budget import detect_cpu_budget
from mily_ai.models import ModelCatalog
from mily_ai.process_memory import process_tree_memory_snapshot_mb
from mily_ai.provider_factory import build_translation_provider
from mily_ai.providers import FasterWhisperAsr
from mily_ai.translation_quality import analyze_translation_quality

catalog = ModelCatalog(models_root)
pack = catalog.active_pack()
if pack is None or pack.id != 'lite-zh-es' or pack.version != '1.0.1':
    raise SystemExit('El pack ZH→ES Lite 1.0.1 no quedó activo')
definition = catalog.definition(pack.id)
components = definition['components']

asr = FasterWhisperAsr(pack.path / 'components' / 'asr', 'cpu')
started = time.perf_counter()
asr.warm_up('zh')
asr_warmup_ms = (time.perf_counter() - started) * 1000.0

speech_executed = False
recognized = ''
if wave_path is not None and wave_path.is_file():
    with wave.open(str(wave_path), 'rb') as source:
        channels = source.getnchannels()
        width = source.getsampwidth()
        rate = source.getframerate()
        raw = source.readframes(source.getnframes())
    if width == 2:
        samples = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
        if channels > 1:
            samples = samples[: samples.size - samples.size % channels].reshape(-1, channels).mean(axis=1)
        if rate != 16000:
            target_length = max(1, round(samples.size * 16000 / rate))
            samples = np.interp(
                np.linspace(0.0, 1.0, num=target_length, endpoint=False),
                np.linspace(0.0, 1.0, num=samples.size, endpoint=False),
                samples,
            ).astype(np.float32)
        segments = asr.transcribe(samples, 'zh')
        recognized = ' '.join(item.text for item in segments if item.text).strip()
        if not recognized:
            raise SystemExit('WHISPER_TINY_ZH_REAL_SPEECH_EMPTY')
        speech_executed = True

translator = build_translation_provider(
    components['translation'],
    pack.path / 'components' / 'translation',
    'cpu',
    detect_cpu_budget('light'),
)
translator.warm_up()
phrases = [
    '你好，会议九点开始。',
    '请确认订单1038，不要取消。',
    '客户需要在五点半之前收到发票。',
    '午饭后我们需要检查网络问题。',
    '麦克风已连接，声音很清楚。',
    '请明天早上发送技术报告。',
]
semantic_rules = {
    phrases[0]: {
        'required': (('reunión', 'reunion'), ('nueve', '9')),
        'forbidden': ('noche', 'madrugada', 'mañana', 'tarde'),
    },
    phrases[1]: {
        'required': (
            ('1038',),
            (' no ', 'nunca', 'sin cancelar', 'no cancele', 'no cancelar'),
        ),
        'forbidden': (),
    },
    phrases[2]: {
        'required': (('cinco', '5'), ('factura',)),
        'forbidden': ('mañana', 'noche', 'madrugada'),
    },
    phrases[3]: {
        'required': (('después', 'despues'), ('almuerzo', 'comida'), ('red', 'network')),
        'forbidden': ('antes del almuerzo', 'antes de comer'),
    },
    phrases[4]: {
        'required': (('micrófono', 'microfono'), ('conectado',), ('claro', 'clara')),
        'forbidden': ('desconectado', 'silencio'),
    },
    phrases[5]: {
        'required': (('mañana',), ('informe', 'reporte'), ('técnico', 'tecnico')),
        'forbidden': ('noche', 'madrugada', 'tarde'),
    },
}


def contains_any(padded_text: str, alternatives: tuple[str, ...]) -> bool:
    return any(value.casefold() in padded_text for value in alternatives)


def sentence_count(value: str) -> int:
    return len([part for part in re.split(r'[.!?。！？]+', value) if part.strip()])


latencies = []
outputs = []
sample_translations = []
quality_reports = []
max_output_words = 0
max_output_sentences = 0
for iteration in range(4):
    for phrase in phrases:
        started = time.perf_counter()
        translated = translator.translate(phrase, 'zh')
        latencies.append((time.perf_counter() - started) * 1000.0)
        if not translated.strip() or translated.strip() == phrase.strip():
            raise SystemExit(f'ZH_ES_TRANSLATION_INVALID: {translated!r}')

        quality = analyze_translation_quality(translated)
        quality_reports.append(quality.as_dict())
        if not quality.passed:
            raise SystemExit(
                'ZH_ES_TRANSLATION_REPETITION: '
                f'{quality.reason} ratio={quality.repeated_ngram_ratio} '
                f'max={quality.max_ngram_occurrences} output={translated!r}'
            )

        padded = f' {" ".join(translated.casefold().split())} '
        rules = semantic_rules[phrase]
        for alternatives in rules['required']:
            if not contains_any(padded, alternatives):
                raise SystemExit(
                    f'ZH_ES_SEMANTIC_INVARIANT: source={phrase!r} '
                    f'alternatives={alternatives!r} output={translated!r}'
                )
        forbidden_hits = [
            value for value in rules['forbidden'] if value.casefold() in padded
        ]
        if forbidden_hits:
            raise SystemExit(
                f'ZH_ES_SEMANTIC_CONTRADICTION: source={phrase!r} '
                f'forbidden={forbidden_hits!r} output={translated!r}'
            )

        words = len(re.findall(r'[^\W_]+', translated, re.UNICODE))
        sentences = sentence_count(translated)
        max_output_words = max(max_output_words, words)
        max_output_sentences = max(max_output_sentences, sentences)
        if words > 24 or sentences > 2:
            raise SystemExit(
                f'ZH_ES_OUTPUT_EXPANSION: words={words} sentences={sentences} '
                f'source={phrase!r} output={translated!r}'
            )

        outputs.append(translated)
        if iteration == 0:
            sample_translations.append({
                'source': phrase,
                'translation': translated,
                'words': words,
                'sentences': sentences,
                'quality': quality.as_dict(),
            })

summary = summarize_latencies(latencies)
memory_snapshot = process_tree_memory_snapshot_mb(os.getpid())
engine_mb = float(memory_snapshot.peak_mb)
product_reserve_mb = 320.0
total_product_mb = engine_mb + product_reserve_mb
max_repeat_ratio = max(
    float(item['repeated_ngram_ratio']) for item in quality_reports
)
max_ngram_occurrences = max(
    int(item['max_ngram_occurrences']) for item in quality_reports
)
report = {
    'schemaVersion': 3,
    'productVersion': '2.0.1',
    'modelPack': f'{pack.id}@{pack.version}',
    'route': 'zh-es',
    'asrWarmupMs': round(asr_warmup_ms, 3),
    'mandarinSpeechFixtureExecuted': speech_executed,
    'recognizedPreview': recognized[:240],
    'sampleTranslations': sample_translations,
    'translation': {
        **summary,
        'preview': outputs[-1][:240],
        'qualityChecks': len(quality_reports),
        'maxRepeatedNgramRatio': round(max_repeat_ratio, 6),
        'maxNgramOccurrences': max_ngram_occurrences,
        'maxOutputWords': max_output_words,
        'maxOutputSentences': max_output_sentences,
        'semanticInvariantsPassed': True,
        'forbiddenTermsPassed': True,
        'expansionLimitsPassed': True,
    },
    'engineWorkingSetMb': round(engine_mb, 3),
    'productReserveMb': product_reserve_mb,
    'totalProductWorkingSetMb': round(total_product_mb, 3),
    'declaredPackRamMb': definition['ramMb'],
    'passed': (
        total_product_mb <= 1536.0
        and float(summary['p95Ms']) <= 1200.0
        and max_repeat_ratio <= 0.25
        and max_ngram_occurrences <= 2
        and max_output_words <= 24
        and max_output_sentences <= 2
    ),
    'notes': [
        'La traducción ZH→ES usa una cascada local ZH→EN→ES con OPUS EN→ES estándar INT8.',
        'El ASR Whisper Tiny multilingüe siempre ejecuta warm-up mandarín real del modelo.',
        'El gate exige seis muestras completas, rechaza contradicciones temporales, expansión y repetición patológica.',
        'mandarinSpeechFixtureExecuted solo es true cuando el runner Windows dispone de una voz SAPI zh-*.'
    ],
}
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('ZH_ES_LITE_ASR_WARMUP_MS', report['asrWarmupMs'])
print('ZH_ES_LITE_MT_P95_MS', summary['p95Ms'])
print('ZH_ES_LITE_TOTAL_PRODUCT_MB', report['totalProductWorkingSetMb'])
print('ZH_ES_LITE_MAX_REPEAT_RATIO', report['translation']['maxRepeatedNgramRatio'])
print('ZH_ES_LITE_MAX_NGRAM_OCCURRENCES', report['translation']['maxNgramOccurrences'])
print('ZH_ES_LITE_MAX_OUTPUT_WORDS', report['translation']['maxOutputWords'])
print('ZH_ES_LITE_MAX_OUTPUT_SENTENCES', report['translation']['maxOutputSentences'])
print('ZH_ES_LITE_SPEECH_FIXTURE', speech_executed)
if total_product_mb > 1536.0:
    raise SystemExit('ZH_ES_LITE_PRODUCT_MEMORY_LIMIT')
if float(summary['p95Ms']) > 1200.0:
    raise SystemExit('ZH_ES_LITE_TRANSLATION_LATENCY_LIMIT')
if not report['passed']:
    raise SystemExit('ZH_ES_LITE_QUALITY_LIMIT')
print('ZH_ES_LITE_GATE_OK')
translator.unload()
asr.unload()
'@ | Set-Content -Path $Probe -Encoding UTF8

    $WaveArg = if ($SpeechFixture) { $MandarinWave } else { '' }
    & $Python $Probe $EngineApp $ModelsRoot $ReportPath $WaveArg
    if ($LASTEXITCODE -ne 0) { throw 'ZH→ES Lite no pasó benchmark de memoria/traducción/calidad.' }
    if (-not (Test-Path $ReportPath -PathType Leaf)) { throw 'ZH→ES Lite no produjo reporte JSON.' }

    Write-Host "ZH→ES LITE OK: $ReportPath" -ForegroundColor Green
}
finally {
    Remove-Item $FixtureRoot -Recurse -Force -ErrorAction SilentlyContinue
}
