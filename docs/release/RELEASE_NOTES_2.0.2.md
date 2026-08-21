# MilyVoiceTraductor 2.0.2

2.0.2 es un hotfix estable de la línea 2.0.x. Corrige el flujo de primer arranque, endurece el instalador NSIS y hace autocontenido el runtime privado en PCs Windows limpias. El baseline de modelos continúa siendo Whisper Small + M2M100 CTranslate2 INT8.

## Primer arranque

- el instalador prepara runtime privado, motor, bridge Native Messaging y extensión;
- **no descarga modelos durante la instalación ni el onboarding**;
- un modelo ausente ya no bloquea el shell de MilyVoiceTraductor;
- al abrir sin modelo activo, la aplicación aterriza en el Gestor de modelos;
- descargar/optimizar/activar un pack requiere acción explícita del usuario;
- un runtime realmente roto continúa enviando al flujo de reparación.

## Instalador Windows

- el NSIS muestra claramente `MilyVoiceTraductor 2.0.2`;
- si `setup-installed.ps1` falla, NSIS establece código de error y aborta;
- ya no puede mostrarse un falso **Installation Complete** después de un bootstrap fallido;
- existe un gate negativo que provoca deliberadamente un fallo del bootstrap y exige que el instalador devuelva un código distinto de cero;
- instalación limpia y reinstalación encima de estado existente se ejecutan con el mismo EXE generado en CI.

## Runtime privado

- Python 3.13 continúa embebido y fijado por SHA-256;
- las DLL obligatorias del Microsoft Visual C++ Runtime se copian app-local junto a `python.exe`: `concrt140.dll`, `msvcp140.dll`, `vcruntime140.dll` y `vcruntime140_1.dll`;
- `runtime-manifest.json` registra archivo, versión y SHA-256 de las DLL app-local;
- el bootstrap vuelve a comprobar esos hashes antes de activar el runtime;
- los imports obligatorios se ejercitan individualmente para descubrir DLL/wheel nativo roto;
- `RUNTIME_IMPORT_FAILED` conserva el nombre del módulo, exit code y resumen sanitizado sin exponer rutas personales ni secretos.

## Validación de modelos y rendimiento

No cambian los pesos de producción:

- ASR: `Systran/faster-whisper-small`;
- MT: `facebook/m2m100_418M` convertido a CTranslate2 INT8.

MegaBench vuelve a ejecutar el pack real en Windows y cubre EN→ES y ZH→ES. El benchmark de GitHub es un gate de regresión; no se presenta como sustituto de un benchmark físico específico sobre cualquier CPU particular.

## Gates obligatorios del mismo SHA

1. consistencia de versión 2.0.2;
2. source verification, privacidad, extensión y GitHub Pages;
3. Frontend typecheck/tests/build;
4. todos los tests Python y `compileall`;
5. Rust format/tests/Clippy Linux;
6. Native Messaging bridge Release;
7. build del runtime Python privado;
8. Visual C++ Runtime app-local + SHA-256;
9. fixture de diagnóstico `RUNTIME_IMPORT_FAILED`;
10. flujo instalado de runtime/bridge/registro;
11. MegaBench real EN→ES y ZH→ES;
12. Rust tests/Clippy Windows;
13. Desktop Release y `WINDOWS_GUI`;
14. bundle Tauri NSIS;
15. prueba negativa: bootstrap roto debe hacer fallar NSIS;
16. instalación limpia: ventana visible y cero descarga/activación implícita durante los primeros segundos;
17. instalación/reinstalación real sobre estado existente;
18. extensión Chromium, SHA256SUMS y artefacto final del mismo commit.

## Compatibilidad y privacidad

CPU sigue siendo el fallback obligatorio. La aceleración solo se considera lista cuando existe una ruta ejecutable. El procesamiento de conversación permanece local en `127.0.0.1`; las sesiones continúan siendo opt-in y no hay telemetría del contenido.

## Historial

- `v2.0.2`: estable corregida;
- `v2.0.1`: estable anterior, conservada como histórico;
- `2.1.x`: canal Beta independiente.

Los binarios no se presentan como Authenticode-firmados mientras no exista una identidad legítima de firma. `SHA256SUMS.txt` verifica integridad del artefacto publicado.
