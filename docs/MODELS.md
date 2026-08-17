# Modelos locales y licencias

MilyVoiceTraductor separa el **código** de los **pesos de IA**. El repositorio no redistribuye pesos; el Model Manager descarga snapshots desde los repositorios declarados en `resources/model-packs.json`, primero a `.staging` y solo activa el pack después de completar la descarga.

## `business-qwen` — recomendado

- ASR: `Systran/faster-whisper-small` (licencia declarada MIT).
- Traducción: `Qwen/Qwen3-0.6B` (licencia declarada Apache-2.0).
- Perfil pensado para el flujo local normal inglés/chino → español.
- Las dos revisiones quedan **fijadas por SHA de commit** en el catálogo de esta release candidate para que una misma versión del pack no cambie silenciosamente con `main`.

## `lite-nllb` — investigación / no comercial

- ASR: `Systran/faster-whisper-small`.
- Traducción: `facebook/nllb-200-distilled-600M`.
- NLLB 600M declara CC-BY-NC-4.0, por lo que MilyVoiceTraductor lo marca explícitamente como **no comercial**.
- También usa revisiones fijadas por commit.

## Seguridad de instalación

- Descarga a staging.
- Revisión exacta fijada en el catálogo.
- Activación mediante `current.json` solo al finalizar.
- Manifiesto SHA-256 local de todos los archivos instalados.
- Verificación posterior desde CLI y escritorio.
- Soporte de rollback al pack anterior.
- No se eliminan packs activos.
- Los modelos viven fuera del directorio de código y no entran en Git ni en el ZIP de fuente.

Antes de convertir una RC en release estable debe conservarse un expediente de release con las licencias de los snapshots fijados y volver a ejecutar las pruebas de traducción/calidad sobre esos mismos commits.
