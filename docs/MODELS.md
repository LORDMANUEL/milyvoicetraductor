# Modelos locales y licencias

MilyVoiceTraductor separa el **código** de los **pesos de IA**. El repositorio no redistribuye pesos; Engine Hub / Model Manager descarga snapshots desde los repositorios declarados en `resources/model-packs.json`, primero a `.staging`, y sólo activa un pack después de descarga, preparación y verificación.

## Perfiles Lite de 2.1.1

Los perfiles Lite son los candidatos para equipos de bajos recursos y se validan con memoria total del producto, RTF P95 y latencia E2E. El presupuesto de referencia del canal 2.1 exige que el producto completo no supere los límites definidos por el Resource Governor; un pack que sólo cabe de forma aislada no es aceptado.

### EN→ES

El canal receptor inglés→español mantiene varios carriles locales para que Engine Hub pueda escoger el que mejor funcione en el hardware disponible:

- `fast-moonshine-en-es` — Moonshine + traducción local;
- `lite-en-es` — Whisper Tiny + traducción local;
- `sherpa-zipformer-en-es` — Sherpa Zipformer + traducción local.

Los tres se prueban de forma real en Windows antes de producir el bundle certificado.

### ES→EN

- Pack: `lite-es-en@1.0.1`.
- ASR: Whisper Tiny multilingüe.
- MT: Marian Tiny ES→EN INT8.
- Es una ruta bloqueante para la certificación 2.1.1.

### ES→ZH

- Pack: `lite-es-zh@1.0.1`.
- ASR: Whisper Tiny multilingüe.
- MT: Marian directo ES→ZH INT8.
- Usa el destino de chino simplificado fijado por el pack.
- Es una ruta bloqueante para la certificación 2.1.1.

### ZH→ES

- Pack: `lite-zh-es@1.0.1`.
- Ruta local Tier 1 disponible.
- Su benchmark Lite continúa **experimental/no bloqueante** para la publicación 2.1.1 y no forma parte del bundle público obligatorio mientras no alcance la promoción correspondiente.

## `realtime-m2m100` — Quality opcional

`realtime-m2m100` conserva la ruta de mayor calidad como opción descargable, pero **no es el perfil Lite recomendado para el presupuesto de 2 GiB**.

- ASR: `Systran/faster-whisper-small`.
- Traducción: `facebook/m2m100_418M`.
- M2M100 se convierte localmente a CTranslate2 INT8.
- La política de 2.1.1 lo rechaza cuando el consumo declarado/medido excede el presupuesto del equipo.
- Sólo debe activarse cuando Engine Hub determine que el hardware tiene recursos suficientes o cuando el usuario lo elija de forma compatible con la política.

## `business-qwen` — alternativa de contexto/calidad

- ASR: `Systran/faster-whisper-small`.
- Traducción: `Qwen/Qwen3-0.6B`.
- Permanece como alternativa manual/R&D; no es el pack automático de primera preparación del canal Lite.
- Las revisiones deben permanecer fijadas por SHA de commit.

## `lite-nllb` — investigación / no comercial

- ASR: `Systran/faster-whisper-small`.
- Traducción: `facebook/nllb-200-distilled-600M`.
- NLLB 600M declara CC-BY-NC-4.0, por lo que MilyVoiceTraductor lo mantiene explícitamente como **no comercial**.
- No forma parte del bundle comercial obligatorio.

## Seguridad de instalación

- Descarga a staging.
- Revisión exacta fijada en el catálogo.
- Activación mediante `current.json` sólo al finalizar.
- Manifiesto SHA-256 local de los archivos instalados.
- Verificación posterior desde CLI y escritorio.
- Soporte de rollback al pack anterior.
- No se eliminan packs activos.
- Los modelos viven fuera del directorio de código y no entran en Git ni en el ZIP de fuente.
- Los packs externos sólo pueden aportar datos/modelos aprobados; ejecutables o scripts no confiables se rechazan.

Cada release debe conservar evidencia de licencias/proveniencia de los snapshots fijados y volver a ejecutar las pruebas de traducción, memoria y rendimiento sobre esos mismos commits.
