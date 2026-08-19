# BetaAlpha — segunda beta del motor

MilyVoice mantiene dos líneas beta independientes para comparar enfoques antes de decidir cuál continuará como base del siguiente motor.

## Beta 1 — Engine Hub

- Rama: `pruebas`
- Enfoque: robustez multi-motor, selección automática, compatibilidad, límites estrictos de 2 GiB y rutas Lite EN→ES/ZH→ES.
- Se mantiene sin sustituir por BetaAlpha.

## Beta 2 — BetaAlpha

- Rama: `betaalpha`
- Enfoque: rendimiento-first.
- Base: parte de Engine Hub Beta y añade VAD previo al ASR, streaming adaptativo por RTF P95, traducción incremental, un solo ASR residente, selección de compute type CTranslate2 por benchmark, runtime Lite separado de Quality, laboratorio ONNX para Moonshine y gate de promoción para un futuro estudiante directo ZH→ES.

## Regla de decisión

Ninguna beta se declara ganadora por arquitectura. Ambas deben ejecutarse con los mismos audios y hardware y compararse en calidad, P50/P95, RTF, RAM estable/pico, CPU, cola, pérdida de finales y estabilidad de sesiones largas. Se seguirá desarrollando la que entregue mejores resultados sin degradar calidad ni privacidad.

## ZH→ES directo

BetaAlpha no activa un modelo directo sin evidencia. La cascada ZH→EN→ES continúa como teacher/fallback. Un estudiante directo debe superar el gate de evaluación antes de entrar a Auto.
