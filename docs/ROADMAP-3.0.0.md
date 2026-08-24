# MilyVoiceTraductor 3.0.0 — Roadmap modular

Estado: **APROBADO PARA EJECUCIÓN POR MÓDULOS**  
Base de compatibilidad: MilyVoice 2.1.x permanece funcional y no se reescribe durante la migración.

## 1. Objetivo

MilyVoice 3.0.0 convierte el producto en una plataforma local modular y versionada. Cada componente tendrá responsabilidad, contrato, versión, pruebas, health y ciclo de release propios. Un componente que alcanza `FROZEN` no se modifica para desarrollar otro componente.

La arquitectura será híbrida: módulos Rust/Python/TypeScript aislados por contrato y procesos separados solamente cuando el aislamiento operativo aporte valor. No se crearán microservicios pesados por defecto porque el producto conserva el objetivo de funcionar dentro de un presupuesto total de 2 GiB de RAM.

## 2. Principios no negociables

1. **2.1.x no se rompe para construir 3.x.**
2. **Un módulo, un propósito, un PR.**
3. **Contrato antes que implementación interna.**
4. **Componente certificado = componente congelado.**
5. **Cambiar un componente no autoriza cambios en otro.**
6. **Los motores se conectan mediante adapters; Desktop no conoce sus internals.**
7. **CPU sigue siendo fallback seguro.**
8. **El producto completo conserva el gate de <= 2 GiB; cada módulo reportará su consumo para poder presupuestarlo.**
9. **No se promociona un modelo sin pesos reales, licencia/proveniencia, hashes y benchmark.**
10. **Stable se genera desde un único SHA reproducible con instalador, extensión, checksums, manifiesto y evidencia.**

## 3. Topología objetivo

```text
apps/
  desktop/
  extension/
  site/

contracts/
  audio/v1/
  realtime/v1/
  compute/v1/
  asr/v1/
  mt/v1/
  tts/v1/
  sessions/v1/
  bridge/v1/

crates/
  mily-supervisor/
  mily-core/
  mily-config/
  mily-system/
  mily-compute/
  mily-audio/
  mily-realtime/
  mily-engine/
  mily-models/
  mily-sessions/
  mily-bridge/
  mily-observability/

services/
  ai/
    engine-host/
    adapters/
      whisper/
      moonshine/
      sherpa/
      external/

manifests/
  milyvoice.components.json
  compatibility.json
```

La migración será incremental: los directorios existentes no se mueven hasta que el contrato del módulo correspondiente esté certificado.

## 4. Catálogo de componentes

| Componente | Responsabilidad | Contrato | Release inicial 3.x |
|---|---|---|---|
| `mily-supervisor` | lifecycle, health, registry, compatibilidad | supervisor/v1 | 1.0.0 |
| `mily-audio` | micrófono, WASAPI, tab, media file | audio/v1 | 1.0.0 |
| `mily-realtime` | buffers, timestamps, backpressure, sincronización | realtime/v1 | 1.0.0 |
| `mily-compute` | hardware probe, benchmark, scoring, fallback | compute/v1 | 2.0.0 |
| `mily-engine-host` | host liviano de motores/adapters IA | engine/v1 | 1.0.0 |
| `mily-asr` | voz a texto | asr/v1 | 1.0.0 |
| `mily-mt` | texto a texto traducido | mt/v1 | 1.0.0 |
| `mily-tts` | texto a voz | tts/v1 | 1.0.0 |
| `mily-linguistic` | normalización, contexto, terminología, segmentación | linguistic/v1 | 1.0.0 |
| `mily-models` | catálogo, descarga, hash, activación, rollback | models/v1 | 2.0.0 |
| `mily-speakers` | diarización y speakers de sesión | speakers/v1 | 1.0.0 |
| `mily-sessions` | sesiones y persistencia consentida | sessions/v1 | 2.0.0 |
| `mily-export` | TXT/SRT/VTT y formatos futuros | export/v1 | 1.0.0 |
| `mily-bridge` | Native Messaging y frontera browser/desktop | bridge/v1 | 2.0.0 |
| `mily-extension` | captura/overlay/control Chrome y Edge | bridge/v1 | 3.0.0 |
| `mily-desktop` | UI, configuración y orquestación | supervisor/v1 | 3.0.0 |
| `mily-updater` | actualización y rollback por componente compatible | updater/v1 | 1.0.0 |
| `mily-observability` | logs, métricas, diagnósticos sanitizados | observability/v1 | 1.0.0 |

## 5. Estados de un componente

```text
EXPERIMENTAL -> DEVELOPMENT -> CANDIDATE -> CERTIFIED -> FROZEN
```

- `EXPERIMENTAL`: no forma parte del release.
- `DEVELOPMENT`: implementación activa, API no congelada.
- `CANDIDATE`: contrato congelado; se permiten correcciones.
- `CERTIFIED`: pasó gates propios y de contrato.
- `FROZEN`: la versión es inmutable. Cualquier mejora crea una versión nueva.

Una versión `FROZEN` jamás se edita en sitio. Ejemplo: si `mily-audio 1.2.0` está congelado, una mejora empieza como `1.3.0-dev` y 1.2.0 continúa disponible para rollback.

## 6. Versionado

MilyVoice usa dos niveles:

```text
Producto: MilyVoice 3.0.0
Componentes: versiones SemVer independientes
```

Un manifiesto de producto fija exactamente la composición:

```json
{
  "product": {"name": "MilyVoiceTraductor", "version": "3.0.0-alpha.1"},
  "components": [
    {"id": "supervisor", "version": "1.0.0", "contract": "supervisor/v1", "stage": "candidate"},
    {"id": "compute", "version": "2.0.0", "contract": "compute/v1", "stage": "frozen"}
  ]
}
```

El release final incluirá este manifiesto y su hash.

## 7. Reglas de dependencia

Dependencias permitidas:

```text
UI/Extension -> Contracts -> Supervisor/Services -> Engine adapters
```

Prohibido:

- Desktop importando internals de Whisper/Moonshine/Sherpa.
- MT leyendo internals de ASR.
- TTS leyendo internals de MT.
- Extension llamando directamente internals Python.
- Un módulo escribiendo el almacenamiento privado de otro.

Toda comunicación cruzada deberá usar un contrato versionado o un tipo público estable del workspace.

## 8. CI 3.0

### Nivel A — Module Gate

Se ejecuta con cada cambio del módulo:

- formato/lint;
- unit tests;
- property/edge tests cuando apliquen;
- memoria y latencia del módulo cuando sea medible;
- seguridad específica;
- artefacto del módulo cuando aplique.

### Nivel B — Contract Gate

Verifica compatibilidad entre productor/consumidor sin requerir acceso a internals.

### Nivel C — Integration Gate

Ejecuta solamente la cadena afectada. Ejemplo: `audio -> realtime -> asr`.

### Nivel D — MegaGate de release

Antes de alpha/beta/RC/stable:

- Frontend/typecheck/tests/build;
- Rust fmt/tests/Clippy;
- Python tests/compile;
- privacidad y source verification;
- Engine Hub;
- política total <= 2 GiB;
- benchmarks reales de motores promocionados;
- desktop Windows;
- `WINDOWS_GUI`;
- NSIS;
- instalación real del NSIS generado;
- extensión Chromium;
- checksums;
- manifiesto de componentes;
- matriz de compatibilidad;
- reporte de certificación.

## 9. Gobierno Git/GitHub

Líneas:

```text
main                producto 2.1.x funcional mientras 3.x migra
release/2.x         mantenimiento 2.x cuando se abra formalmente
v3/*                 módulos y arquitectura 3.x
```

Reglas de PR:

- nunca programar directamente en `main`;
- un PR debe declarar el módulo propietario;
- evitar cambios cruzados;
- cambios de contrato requieren prueba de compatibilidad;
- un PR de módulo no cambia `VERSION` global;
- MegaGate solamente fusiona una composición 3.x cuando todas sus dependencias están certificadas.

## 10. Roadmap de ejecución

### F0 — Baseline 2.1.x

**Objetivo:** conservar una referencia funcional y reproducible.

Salida:
- SHA funcional documentado;
- CI verde;
- artefactos y checksums verificables;
- 3.x arranca desde rama aislada.

Gate: ningún commit 3.x rompe `main`.

### F1 — Foundation / Supervisor

**Objetivo:** crear gobierno técnico de componentes.

Entregables:
- `mily-supervisor`;
- tipos de manifiesto;
- validación de IDs/versiones/contratos;
- stages;
- health registry;
- rechazo de health para componentes desconocidos;
- documento de compatibilidad y roadmap.

Release de módulo: `mily-supervisor 1.0.0-candidate`.

### F2 — Contracts Kernel

Entregables:
- directorio `contracts/`;
- esquema de versionado de contratos;
- pruebas consumidor/productor;
- policy de breaking change.

Gate: contrato v1 no cambia de forma incompatible sin nueva major.

### F3 — MilyCompute 2.x

Entregables:
- profiler;
- backend registry;
- compatibility filter;
- benchmark/scoring;
- presupuesto memoria/cómputo;
- CPU fallback;
- cache de selección.

Gate: `mily-compute 2.0.0 FROZEN` antes de modificar Engine Host.

### F4 — Audio 1.x

Entregables:
- micrófono;
- WASAPI loopback;
- browser/tab bridge;
- media file;
- formato PCM contractual;
- resample y timestamps.

Gate: audio continuo sin pérdida deliberada y sin crecimiento de memoria.

### F5 — Realtime 1.x

Entregables:
- bounded queues;
- backpressure;
- sequence IDs;
- clock/timestamps;
- jitter/desync control;
- stress tests largos.

Gate: no desfase progresivo de frases bajo fixture controlado.

### F6 — Engine Host 1.x

Entregables:
- un único host liviano;
- plugin/adapters;
- discovery;
- load/unload;
- health;
- aislamiento de fallo.

Gate: fallo de un adapter no derriba Supervisor/Desktop.

### F7 — ASR 1.x

Adapters promocionados inicialmente:
- Whisper;
- Moonshine;
- Sherpa/Zipformer donde soporte el idioma requerido.

Gate: contrato ASR, RTF, P50/P95 y memoria dentro del perfil correspondiente.

### F8 — Linguistic 1.x + MT 1.x

Fast paths prioritarios:
- EN -> ES;
- ZH -> ES;
- ES -> EN;
- ES -> ZH.

Gate: números, negaciones, nombres y terminología crítica sin regresión frente al baseline aprobado.

### F9 — TTS 1.x

Entregables:
- cola TTS;
- voces por idioma/speaker;
- ducking;
- anti-feedback;
- fallback a subtítulos si TTS falla.

Gate: TTS puede deshabilitarse/reiniciarse sin interrumpir ASR/MT.

### F10 — Model Manager 2.x

Entregables:
- download/resume;
- hashes;
- licencia/proveniencia;
- activate atomically;
- rollback;
- external model inspection;
- benchmark previo a promoción.

Gate: un modelo corrupto o incompatible nunca reemplaza el modelo activo.

### F11 — Speakers/Sessions/Export

Entregables:
- speakers A/B/C;
- aliases y configuración efímera;
- sesiones;
- TXT/SRT/VTT bilingüe;
- persistencia solo con consentimiento.

Gate: privacidad y recuperación de sesión pasan sus tests propios.

### F12 — Bridge + Extension 3.0

Entregables:
- Native Messaging contract;
- captura tab;
- overlay;
- detección sitio/modo;
- reconexión;
- extensión sin lógica de inferencia.

Gate: actualizar extensión no requiere recompilar ASR/MT.

### F13 — Desktop 3.0

Entregables:
- dashboard de componentes;
- selección automática/manual;
- health/version/status;
- recursos;
- diagnóstico;
- modos Reunión/Educativo/Karaoke/Compacto.

Gate: Desktop solo consume APIs públicas/contratos.

### F14 — Updater 1.x

Entregables:
- manifest firmado/hashado;
- compatibility matrix;
- actualización selectiva;
- rollback;
- canal stable/beta/alpha.

Gate: actualización incompatible se rechaza antes de modificar archivos activos.

### F15 — Observability 1.x

Entregables:
- health snapshot;
- logs sanitizados;
- latencia y memoria por módulo;
- restart count;
- export diagnóstico sin audio/transcripción por defecto.

### F16 — Release trains

Alphas:
1. `3.0.0-alpha.1`: Foundation + Supervisor + Contracts.
2. `3.0.0-alpha.2`: Compute + Audio.
3. `3.0.0-alpha.3`: Realtime + Engine Host.
4. `3.0.0-alpha.4`: ASR + MT + Linguistic + TTS.
5. `3.0.0-alpha.5`: Desktop + Extension + Sessions + Updater integrados.

Betas:
- `beta.1`: funcionalidad completa, bugs permitidos;
- `beta.2`: rendimiento/recursos/compatibilidad;
- `beta.3`: freeze funcional y release rehearsal.

RC:
- `rc.1+`: feature freeze; solo bugs, seguridad, rendimiento regresivo y packaging.

Stable:
- `3.0.0`: todos los módulos requeridos `CERTIFIED` o `FROZEN`, MegaGate verde en el mismo SHA.

## 11. Artefactos obligatorios de 3.0.0 Stable

```text
MilyVoice-3.0.0-Windows-x64.exe
MilyVoice-Extension-3.0.0.zip
component-manifest.json
compatibility-matrix.json
module-certification.json
MegaBench-report.json
SHA256SUMS.txt
SBOM
```

## 12. Definition of Done de cada módulo

Un componente no puede declararse `CERTIFIED` sin:

- unit tests PASS;
- contract tests PASS;
- integración afectada PASS;
- lint/static analysis PASS;
- resource gate definido y PASS;
- errores/fallback probados;
- versión y API declaradas;
- changelog del componente;
- evidencia CI vinculada a SHA;
- rollback o estrategia segura cuando maneje estado/artefactos.

## 13. Orden inmediato de trabajo

```text
F1 Supervisor
 -> F2 Contracts
 -> F3 Compute
 -> F4 Audio
 -> F5 Realtime
 -> F6 Engine Host
 -> F7 ASR
 -> F8 Linguistic/MT
 -> F9 TTS
 -> F10 Models
 -> F11 Sessions
 -> F12 Bridge/Extension
 -> F13 Desktop
 -> F14 Updater
 -> F15 Observability
 -> F16 Release trains
```

No se inicia un módulo dependiente si el contrato del módulo anterior no está al menos en `CANDIDATE`.