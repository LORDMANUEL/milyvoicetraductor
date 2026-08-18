# Modelos locales y licencias

MilyVoiceTraductor separa el **código** de los **pesos de IA**. El repositorio no redistribuye pesos; el Model Manager descarga snapshots desde los repositorios declarados en `resources/model-packs.json`, primero a `.staging` y solo activa el pack después de completar descarga, preparación y verificación.

## `realtime-m2m100` — recomendado

- ASR: `Systran/faster-whisper-small` (licencia declarada MIT).
- Traducción: `facebook/m2m100_418M`.
- M2M100 se descarga desde Hugging Face con revisión fijada y se convierte localmente a CTranslate2 INT8 una sola vez.
- Perfil pensado para subtítulos inglés/chino → español con menor memoria y latencia de ejecución que el modelo Transformer original.
- La app muestra las fases **descarga ASR → descarga traducción → optimización INT8 → verificación → listo**.
- La operación se ejecuta sin consola externa en Windows.

## `business-qwen` — alternativa de contexto/calidad

- ASR: `Systran/faster-whisper-small` (licencia declarada MIT).
- Traducción: `Qwen/Qwen3-0.6B` (licencia declarada Apache-2.0).
- Permanece disponible como alternativa manual; no es el pack automático de primera preparación en 1.0.5.
- Las dos revisiones quedan fijadas por SHA de commit.

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

Cada release estable debe conservar un expediente de licencias de los snapshots fijados y volver a ejecutar las pruebas de traducción/calidad sobre esos mismos commits.
