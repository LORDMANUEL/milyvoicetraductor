# MilyVoice BetaAlpha — Performance-first Engine

BetaAlpha es una línea experimental separada de **Engine Hub Beta**. Las dos se mantienen en paralelo y se comparan con los mismos audios, hardware y gates; no se fusionan por intuición.

## Hipótesis

BetaAlpha prioriza hacer menos trabajo por segundo de audio: VAD barato antes del ASR, streaming adaptativo por RTF P95, traducción incremental por prefijos, un solo ASR residente y selección de compute type por microbenchmark.

## Objetivos de ingeniería

- idle < 250 MiB;
- EN→ES completo < 700 MiB;
- ZH→ES < 900 MiB cuando exista estudiante directo promovido;
- pico Lite < 1.2 GiB;
- primera parcial <= 350 ms cuando el hardware lo permita;
- final visible <= 800 ms;
- cola final <= 2 utterances;
- cero pérdida de finales en 10 minutos.

## Cambios BetaAlpha

1. `AdaptiveStreamingController`: 280/450/700/800 ms según RTF P95 y presión.
2. `VadGate`: RMS pre-ASR con pre-roll de 160 ms.
3. `IncrementalTranslationPlanner`: reutiliza prefijos estables y traduce solo la cola nueva.
4. `EngineResidencyPolicy`: un ASR caliente; candidatos alternos permanecen en disco.
5. `ComputeTypeSelector`: permite elegir entre tipos CT2 soportados por benchmark del equipo.
6. Runtime Lite separado de Torch/Transformers/Quality.
7. Model Lab ZH→ES directo: el estudiante no puede reemplazar la cascada hasta >=200 muestras, >=97% de calidad relativa, P95 <=220 ms y <=900 MiB.
8. Moonshine ORT/INT8 es experimental y solo se promueve si conserva >=99% de calidad y gana >=5% latencia o >=10% memoria.

## Dos betas, dos enfoques

- **Engine Hub Beta (`pruebas`)**: robustez multi-motor, compatibilidad y selección segura.
- **BetaAlpha (`betaalpha`)**: rendimiento-first, trabajo incremental, runtime mínimo y experimentos de distillation/quantization.

La línea que gane los benchmarks de calidad, P95, RTF, memoria y estabilidad será la base del siguiente desarrollo.

## Importante sobre ZH→ES directo

No se activa un modelo directo inexistente o no certificado. La cascada actual sigue siendo el teacher/fallback. BetaAlpha incorpora el gate y la arquitectura para entrenar/evaluar un estudiante directo; solo un artefacto que supere los gates puede entrar a Auto.
