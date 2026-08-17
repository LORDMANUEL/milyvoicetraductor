# Instalación de MilyVoiceTraductor

## Objetivo de distribución

MilyVoiceTraductor se distribuye en dos piezas independientes:

1. **Desktop Tauri**: interfaz, configuración, SQLite, caché, logs y control de procesos.
2. **Motor IA local**: Python/sidecar y pesos de modelos. Los pesos se descargan después de instalar porque son grandes y cada modelo conserva su propia licencia.

## Windows — desarrollo / instalación desde fuente

Abra PowerShell en la raíz del proyecto:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\installer\windows\setup-source.ps1 -InstallPythonIfMissing -ModelPack business-qwen
```

El script:

- usa Python 3.13;
- si se autoriza con `-InstallPythonIfMissing`, puede solicitar a `winget` instalar Python para el usuario actual;
- crea un runtime aislado en `%LOCALAPPDATA%\MilyVoiceTraductor\engine\python`;
- copia e instala el motor IA;
- ejecuta `diagnose`;
- descarga el pack seleccionado en `%LOCALAPPDATA%\MilyVoiceTraductor\models`;
- prepara la extensión Chromium en `%LOCALAPPDATA%\MilyVoiceTraductor\extension`.

Para preparar el runtime sin descargar pesos:

```powershell
.\installer\windows\setup-source.ps1 -InstallPythonIfMissing -SkipModelDownload -ModelPack none
```

## Extensión Chromium

```powershell
.\installer\windows\install-extension.ps1
```

Después abra `chrome://extensions` o `edge://extensions`, active **Modo desarrollador**, pulse **Cargar descomprimida** y seleccione la carpeta mostrada por el script.

La extensión no empieza a capturar audio al instalarse. El navegador concede los permisos declarados por Manifest V3 y la captura de pestaña solo inicia después de una acción explícita sobre **Iniciar traducción**.

## Compilar el desktop

```powershell
.\installer\windows\build-release.ps1 -SkipRuntimeSetup
```

El script ejecuta typecheck, pruebas frontend, build Vite, pruebas Rust, Clippy y `tauri build` para producir el instalador NSIS.

## Sidecar compilado opcional

Para una release donde el usuario no necesite un runtime Python administrado:

```powershell
.\installer\windows\build-ai-sidecar.ps1
```

El resultado se coloca en `dist\sidecar\mily-ai-engine.exe`. Los pesos de modelos continúan fuera del ejecutable.
