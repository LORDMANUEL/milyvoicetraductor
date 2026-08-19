# MilyVoiceTraductor — Beta Engine Hub 2.1

> **Estado:** Beta / Testing. No sustituye todavía la versión estable `v2.0.1` de `main`.

La rama `pruebas` contiene la evolución Engine Hub orientada a menor latencia, menor consumo de RAM, selección automática de motores y diagnóstico reparable. Un SHA solo se considera candidato instalable cuando completa el mismo MegaGate Windows; resultados verdes de commits anteriores no se mezclan.

## Objetivos de esta beta

- producto completo por debajo de 2 GiB y perfil Lite con margen amplio;
- CPU-only como ruta de primera clase, incluida referencia 2C/4T;
- GPU de 512 MiB opcional, nunca obligatoria;
- Moonshine/Whisper Tiny y rutas Tier 1 EN→ES / ZH→ES bajo gates comunes;
- cero crecimiento continuo de cola y cero finales perdidos;
- instalador NSIS real, reinstalación y reparación verificables;
- errores con códigos estables y evidencia diagnóstica sanitizada.

## Optimización de traducción

La escucha/ASR y la traducción se miden por separado. En equipos dual-core, ASR y MT comparten un executor serial: ambos pueden reutilizar los dos cores físicos sin ejecutarse simultáneamente. Los parciales ingleses no se envían a MT si todavía terminan en un modal/conector incompleto; mandarín conserva estabilización incremental por caracteres Han.

Marian EN→ES mantiene greedy search como primer pase. Solo ejecuta un segundo decode acotado cuando detecta repetición patológica o pérdida de información crítica determinista, actualmente números y negaciones. Esto evita pagar mayor latencia en frases normales y reduce resultados incongruentes de alto impacto.

## Diagnóstico y reparación

MilyVoice mantiene dos niveles de evidencia local:

- `milyvoice.log`: log humano rotado y sanitizado;
- `repair-history.jsonl`: eventos estructurados de reparación, también rotados y sanitizados.

Cada reparación usa un `incidentId` común y registra `Started`, `Succeeded` o `Failed`, además de componente, etapa, código público, mensaje y acción recomendada. Se eliminan tokens, contraseñas, correos y homes de usuario antes de persistir.

Desktop incluye **Diagnóstico y reparación**, donde se muestran los eventos recientes y se puede ejecutar la reparación controlada sin abrir PowerShell visible.

El bootstrap Windows diferencia módulos base de adapters opcionales. Un adapter opcional que no pueda cargar en una PC concreta no debe impedir abrir MilyVoice; se registra y Engine Hub utiliza fallback. Los componentes base sí bloquean y entregan un código concreto.

## Evidencia CI incluso cuando falla

El Windows gate conserva un artefacto `MilyVoiceTraductor-Diagnostics-<sha>` con evidencia sanitizada aunque la certificación falle antes de generar el EXE. Puede incluir:

- salida de tests AI;
- benchmarks parciales;
- `runtime-manifest.json`;
- `bootstrap/status.json`;
- logs MilyVoice/AI/repair-history generados por el runner;
- contexto mínimo de run y SHA.

Nunca se exportan variables de entorno, tokens ni credenciales.

## MegaGate obligatorio

Un único SHA debe pasar:

1. Source/Privacy/Extension/Site guards.
2. Python unit + realtime contracts.
3. Frontend typecheck/tests/build.
4. Rust format/tests/Clippy Linux y Windows.
5. Runtime Python privado y Native Messaging.
6. Simulación de máquina objetivo 2 GiB.
7. Moonshine Lite EN→ES real.
8. Whisper Tiny Lite EN→ES real.
9. Mandarin Lite ZH→ES real.
10. Desktop Release y `WINDOWS_GUI`.
11. Tauri NSIS.
12. Instalación limpia del NSIS real.
13. Reinstalación sobre runtime previo activo.
14. Extensión Chromium, benchmarks y SHA-256.

Hasta que ese mismo SHA complete todo, el PR permanece Draft y `main` continúa en v2.0.1.

## Candidato actual

El SHA se fija en el comentario de coordinación de PR #11. Durante una certificación no se permiten nuevos pushes a `pruebas`; si falla un gate, se corrige únicamente la causa comprobada y el nuevo SHA vuelve a ejecutar el MegaGate completo.
