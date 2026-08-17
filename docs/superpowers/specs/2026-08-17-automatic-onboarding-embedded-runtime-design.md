# MilyVoiceTraductor — Onboarding automático y runtime embebido

Fecha: 2026-08-17
Estado: aprobado para implementación

## Objetivo

Eliminar la configuración manual entre la aplicación de escritorio y la extensión Chromium, y eliminar la dependencia del equipo del usuario de Python/winget/pip durante la instalación normal. El usuario instala MilyVoiceTraductor y la extensión; ambas piezas se reconocen automáticamente de forma local y segura.

## Problema confirmado

La RC1 actual puede instalar la interfaz aunque falle la preparación del motor local. El bootstrap intenta descubrir o instalar Python 3.13, crear un venv, ejecutar `pip install`, diagnosticar el motor y descargar el modelo durante el post-install. Si cualquiera de esas operaciones falla, la aplicación queda instalada pero el motor aparece como `No instalado`.

El Model Manager agrava el diagnóstico porque ejecuta la CLI del motor con stdout/stderr descartados y transforma distintos fallos en un único mensaje genérico. La extensión también requiere copiar manualmente token y puerto.

Los commits fijados de `Systran/faster-whisper-small` y `Qwen/Qwen3-0.6B` existen actualmente en Hugging Face, por lo que el diseño no debe asumir que el fallo mostrado procede de una revisión inexistente. La instalación debe exponer la causa concreta cuando una descarga o preparación falle.

## Experiencia final del usuario

### Instalación

1. Ejecutar `MilyVoiceTraductor Setup.exe`.
2. El instalador instala el desktop y un runtime privado completo.
3. El instalador registra el Native Messaging Host para navegadores Chromium soportados.
4. La extensión se instala/carga como segunda pieza.
5. Desktop y extensión se reconocen automáticamente.
6. La aplicación descarga el pack recomendado en segundo plano con progreso, pausa/reintento y verificación.
7. Cuando el modelo queda listo, el producto muestra `Listo para traducir`.

No se pide al usuario:

- instalar Python;
- usar winget;
- ejecutar pip;
- introducir puertos;
- copiar/pegar tokens;
- ejecutar PowerShell;
- entrar al Model Manager para completar la instalación inicial.

## Runtime Python privado

### Decisión

El instalador incluirá un runtime Python 3.13 x64 privado preparado para MilyVoiceTraductor. No se utilizará el Python del sistema como dependencia de producción.

La aplicación conservará Python únicamente como implementación interna del motor IA. El usuario no administra ese runtime.

### Ubicación

```text
%LOCALAPPDATA%\MilyVoiceTraductor\
├── runtime\
│   └── python\
├── engine\
├── bridge\
├── extension\
├── models\
├── config\
├── cache\
├── logs\
└── bootstrap\
```

### Requisitos

- El build de release prepara el runtime antes de construir NSIS.
- Las dependencias Python necesarias se congelan y se instalan en staging durante CI/build, no en el PC del usuario.
- El instalador copia el runtime ya preparado.
- No se invoca `winget` en el flujo normal.
- No se ejecuta `pip install` contra Internet durante la instalación normal.
- Se verifica integridad de los archivos del runtime incluidos en la release.

## Modelos

Los pesos siguen separados del EXE porque son grandes y conservan sus licencias propias.

### Primera ejecución

El desktop detecta que `business-qwen` no está instalado y abre automáticamente el onboarding:

```text
Preparando MilyVoiceTraductor

Runtime           ✓
Motor local       ✓
Navegador         ✓ / esperando extensión
Modelo IA         38%  724 MB / 1.9 GB
Verificación      pendiente

[Reintentar] [Continuar en segundo plano]
```

### Descargas

El Model Downloader debe:

- descargar a staging;
- soportar reanudación cuando el proveedor lo permita;
- conservar archivos parciales válidos;
- comprobar espacio libre antes de comenzar;
- distinguir ausencia de Internet, HTTP/provider, falta de espacio, hash/integridad y permisos;
- activar `current.json` solo cuando el pack esté completo;
- conservar rollback;
- no mostrar un mensaje genérico para causas distintas.

### Códigos públicos

Como mínimo:

- `MODEL_NO_NETWORK`
- `MODEL_NO_SPACE`
- `MODEL_PROVIDER_ERROR`
- `MODEL_DOWNLOAD_INTERRUPTED`
- `MODEL_HASH_MISMATCH`
- `MODEL_RUNTIME_ERROR`
- `MODEL_PERMISSION_ERROR`
- `MODEL_LICENSE_BLOCKED`

Cada código tiene un mensaje de usuario y un diagnóstico técnico sanitizado separado.

## Auto-reconocimiento Desktop ↔ Extensión

### Native Messaging

Se utilizará Chrome Native Messaging como canal de descubrimiento y control local.

Host lógico:

```text
com.milyvoice.traductor
```

El instalador crea el manifiesto Native Messaging y registra su ruta bajo HKCU para los navegadores soportados.

El manifiesto usa `allowed_origins` explícitos. No se permiten wildcards.

### Host nativo

Se implementará un ejecutable ligero en Rust:

```text
milyvoice-bridge.exe
```

Responsabilidades:

- protocolo Native Messaging stdin/stdout con framing de 32 bits;
- validar origen permitido;
- descubrir estado del desktop/runtime;
- proporcionar puerto local y credencial efímera a la extensión;
- iniciar el motor local si está detenido;
- informar modelo activo y versión;
- nunca enviar audio por Native Messaging;
- nunca escribir token en logs.

### Extensión

La extensión elimina de su interfaz normal:

- campo `Token de emparejamiento`;
- campo `Puerto local`.

Al abrirse:

```text
chrome.runtime.connectNative("com.milyvoice.traductor")
```

El bridge responde:

```json
{
  "protocol": 1,
  "desktop": "ready",
  "engine": "ready",
  "port": 8765,
  "credential": "<efímera>",
  "modelPack": "business-qwen@1.0.0"
}
```

La credencial efímera no se presenta al usuario y tiene vida corta.

### Estado visual

```text
MilyVoiceTraductor
✓ Aplicación detectada
✓ Motor local activo
✓ Modelo listo

Origen  [Automático]
Destino [Español]

[Iniciar traducción]
```

Si falta desktop:

```text
MilyVoiceTraductor no está instalado.
[Descargar aplicación]
```

Si falta el modelo:

```text
Aplicación conectada
Preparando modelo: 46%
```

## WebSocket

El audio mantiene el flujo WebSocket en loopback. Native Messaging se usa para bootstrap/emparejamiento/control, no para transportar audio continuo.

```text
Extension
  │ connectNative
  ▼
Rust bridge
  │ estado + credencial temporal
  ▼
127.0.0.1:8765
  ▲
  │ WebSocket PCM16
Extension offscreen
```

## Seguridad

- loopback exclusivamente para el motor;
- Native Messaging restringido a IDs de extensión autorizados;
- credenciales efímeras generadas por sesión;
- no exponer secretos en UI;
- no guardar secretos en logs;
- no usar `<all_urls>`;
- no telemetría;
- audio nunca se transporta mediante Internet por MilyVoiceTraductor;
- modelos son la única descarga externa requerida para funcionamiento IA.

## Instalador NSIS

El post-install deja de instalar Python y dependencias desde Internet.

El instalador deberá:

1. instalar Desktop Tauri;
2. copiar runtime Python preconstruido;
3. copiar engine;
4. instalar `milyvoice-bridge.exe`;
5. copiar extensión;
6. registrar Native Messaging para Chrome/Edge/Brave cuando estén presentes;
7. crear estado inicial;
8. abrir el Desktop;
9. dejar al Desktop administrar la descarga del modelo.

El setup no se queda congelado durante una descarga de varios GB.

## Diagnóstico y recuperación

Se crea `BootstrapStatusService` con estados estructurados:

```text
runtimeReady
bridgeReady
extensionDetected
modelState
engineState
lastErrorCode
lastErrorMessage
```

La aplicación incluye una acción `Reparar instalación` que vuelve a validar runtime, bridge, registro Native Messaging y modelo sin reinstalar el desktop completo.

## Tests obligatorios

### Python/modelos

- descarga simulada completa;
- interrupción y reintento;
- falta de espacio;
- hash inválido;
- provider failure;
- staging nunca se activa parcialmente.

### Rust

- Native Messaging framing;
- request/response;
- origen no permitido;
- descubrimiento runtime;
- generación de credencial efímera;
- credencial expirada/reutilizada rechazada;
- ModelManager conserva stderr sanitizado y código de error.

### Extensión

- sin campos manuales de token/puerto;
- `connectNative` al iniciar popup;
- desktop ausente muestra CTA de instalación;
- desktop presente obtiene configuración automática;
- captura sigue requiriendo acción explícita del usuario.

### Windows CI

- validar runtime staging;
- validar que `python.exe` privado existe dentro del bundle preparado;
- ejecutar `python --version` desde el runtime privado;
- importar módulos requeridos desde ese runtime;
- test Native Messaging host con stdin/stdout real;
- verificar claves de registro usando hive de prueba/script controlado;
- construir NSIS;
- instalar silenciosamente en Windows runner o VM cuando sea posible;
- ejecutar smoke test post-install;
- desinstalar y verificar limpieza.

## UI

El onboarding sustituye el flujo manual actual.

Model Manager permanece disponible como herramienta administrativa después de la instalación, pero ya no es requisito para empezar.

La pantalla Traducción en vivo deja de mostrar o copiar tokens. Solo muestra estado de sincronización:

- navegador detectado;
- motor;
- modelo;
- listo/no listo.

## Repositorio y ramas

Política desde esta implementación:

- `main`: versión publicada y validada;
- `pruebas`: desarrollo, correcciones y CI previo a integración.

No se crearán nuevas ramas `agent/*`, `feat/*`, `tmp-*` o equivalentes para el flujo normal.

Después de que `pruebas` se valide y se integre, se eliminarán las ramas antiguas ya fusionadas, conservando únicamente `main` y `pruebas`.

## GitHub Pages

Se mantiene una sola landing en `apps/site` y un solo workflow Pages.

La landing enlaza siempre a la release validada actual.

## Criterios de aceptación

La mejora no se considera terminada hasta que:

1. Una instalación Windows limpia no necesite Python preinstalado.
2. El instalador no invoque winget/pip contra Internet para preparar el runtime.
3. El runtime privado ejecute el motor correctamente.
4. Desktop y extensión se detecten sin copiar token ni puerto.
5. La extensión no muestre esos campos en flujo normal.
6. El modelo recomendado pueda descargarse/reintentarse desde onboarding con causa de error específica.
7. Un modelo incompleto nunca quede activo.
8. El desktop pueda reparar una preparación fallida.
9. Todos los tests Linux/Windows, frontend, Python, Rust, Clippy y privacidad pasen.
10. NSIS se genere y el smoke test post-install pase en Windows CI.
11. Pages publique únicamente `apps/site`.
12. `main` y `pruebas` sean las únicas ramas de trabajo activas tras la limpieza final.
