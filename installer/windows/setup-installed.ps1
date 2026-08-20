[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallRoot,
    [string]$AppRoot = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$env:HF_HUB_DISABLE_TELEMETRY = '1'

$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$BootstrapRoot = Join-Path $InstallRoot 'bootstrap'
$RuntimeZip = Join-Path $BootstrapRoot 'runtime\milyvoice-python-runtime.zip'
$RuntimeHash = Join-Path $BootstrapRoot 'runtime\milyvoice-python-runtime.zip.sha256'
$EngineSource = Join-Path $BootstrapRoot 'ai'
$ExtensionSource = Join-Path $BootstrapRoot 'extension'
$BridgeSource = Join-Path $BootstrapRoot 'bridge\milyvoice-bridge.exe'
$RegisterScript = Join-Path $BootstrapRoot 'register-native-host.ps1'
$NativeTemplate = Join-Path $BootstrapRoot 'native-host-template.json'

if ([string]::IsNullOrWhiteSpace($AppRoot)) {
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        Write-Error 'APPDATA_ROOT_MISSING: Windows no proporcionó LOCALAPPDATA y no se indicó AppRoot.'
        exit 1
    }
    $AppRoot = Join-Path $env:LOCALAPPDATA 'MilyVoiceTraductor'
}
$AppRoot = [System.IO.Path]::GetFullPath($AppRoot)

$RuntimeParent = Join-Path $AppRoot 'runtime'
$RuntimeRoot = Join-Path $RuntimeParent 'python'
$RuntimeNext = Join-Path $RuntimeParent 'python.next'
$EngineApp = Join-Path $AppRoot 'engine\app'
$ExtensionRoot = Join-Path $AppRoot 'extension'
$BridgeRoot = Join-Path $AppRoot 'bridge'
$BridgeTarget = Join-Path $BridgeRoot 'milyvoice-bridge.exe'
$NativeManifest = Join-Path $BridgeRoot 'com.milyvoice.traductor.json'
$ConfigRoot = Join-Path $AppRoot 'config'
$CacheRoot = Join-Path $AppRoot 'cache'
$ModelsRoot = Join-Path $AppRoot 'models'
$BootstrapStateRoot = Join-Path $AppRoot 'bootstrap'
$StatusPath = Join-Path $BootstrapStateRoot 'status.json'
$script:BootstrapStage = 'BOOTSTRAP_START'
$script:OptionalRuntimeUnavailable = @()

$DefaultRequiredRuntimeModules = @(
    'fastapi',
    'uvicorn',
    'numpy',
    'faster_whisper',
    'ctranslate2',
    'huggingface_hub',
    'sentencepiece'
)
$DefaultOptionalRuntimeModules = @(
    'transformers',
    'torch',
    'moonshine_voice',
    'sherpa_onnx',
    'onnxruntime',
    'vosk',
    'google.cloud.speech_v2',
    'pyaudiowpatch'
)

function Write-Step([string]$Text) {
    Write-Host "[MilyVoiceTraductor] $Text"
}

function Write-BootstrapStatus([string]$State, [string]$Code, [string]$Message) {
    New-Item -ItemType Directory -Force -Path $BootstrapStateRoot | Out-Null
    [ordered]@{
        schemaVersion = 3
        state = $State
        code = $Code
        message = $Message
        stage = $script:BootstrapStage
        optionalUnavailable = @($script:OptionalRuntimeUnavailable)
        updatedAt = (Get-Date).ToUniversalTime().ToString('o')
    } | ConvertTo-Json -Depth 5 | Set-Content -Path $StatusPath -Encoding UTF8
}

function Set-BootstrapStage([string]$Code, [string]$Message) {
    $script:BootstrapStage = $Code
    Write-BootstrapStatus 'installing' $Code $Message
}

function Assert-File([string]$Path, [string]$Code) {
    if (-not (Test-Path $Path -PathType Leaf)) {
        throw "$Code|Falta un componente incluido en el instalador."
    }
}

function Get-Sha256Hex([string]$Path) {
    $stream = $null
    $sha = $null
    try {
        $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
        $sha = [System.Security.Cryptography.SHA256]::Create()
        $bytes = $sha.ComputeHash($stream)
        return ([System.BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
    } finally {
        if ($sha -ne $null) { $sha.Dispose() }
        if ($stream -ne $null) { $stream.Dispose() }
    }
}

function Read-ExpectedSha256([string]$Path) {
    try {
        $text = [System.IO.File]::ReadAllText($Path).Trim()
    } catch {
        throw 'RUNTIME_HASH_FILE_INVALID|No se pudo leer la firma SHA-256 incluida con el runtime.'
    }
    if ([string]::IsNullOrWhiteSpace($text)) {
        throw 'RUNTIME_HASH_FILE_INVALID|La firma SHA-256 incluida con el runtime está vacía.'
    }
    $candidate = ($text -split '\s+')[0].Trim().ToLowerInvariant()
    if ($candidate -notmatch '^[0-9a-f]{64}$') {
        throw 'RUNTIME_HASH_FILE_INVALID|La firma SHA-256 incluida con el runtime no tiene un formato válido.'
    }
    return $candidate
}

function Copy-DirectoryContents([string]$Source, [string]$Destination, [string]$Code) {
    if (-not (Test-Path $Source -PathType Container)) {
        throw "$Code|No se encontró una carpeta incluida en el instalador."
    }
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $Source -Force) {
        $target = Join-Path $Destination $item.Name
        Copy-Item -LiteralPath $item.FullName -Destination $target -Recurse -Force
    }
}

function Expand-RuntimeArchive([string]$Archive, [string]$Destination) {
    Remove-Item $Destination -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null

    $windowsRoot = if ([string]::IsNullOrWhiteSpace($env:WINDIR)) { 'C:\Windows' } else { $env:WINDIR }
    $systemDirectory = if (-not [string]::IsNullOrWhiteSpace($env:PROCESSOR_ARCHITEW6432)) {
        Join-Path $windowsRoot 'Sysnative'
    } else {
        Join-Path $windowsRoot 'System32'
    }
    $tar = Join-Path $systemDirectory 'tar.exe'

    if (Test-Path $tar -PathType Leaf) {
        & $tar -xf $Archive -C $Destination
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Remove-Item $Destination -Recurse -Force -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    }

    try {
        Expand-Archive -Path $Archive -DestinationPath $Destination -Force
    } catch {
        throw 'RUNTIME_EXTRACT_FAILED|No se pudo extraer el runtime privado incluido en el instalador.'
    }
}

function Stop-MilyVoiceOwnedProcesses {
    $ownedPaths = @(
        (Join-Path $RuntimeRoot 'python.exe'),
        $BridgeTarget
    ) | ForEach-Object { [System.IO.Path]::GetFullPath($_) }

    try {
        $processes = Get-CimInstance Win32_Process -ErrorAction Stop
    } catch {
        throw 'RUNTIME_PROCESS_QUERY_FAILED|No se pudieron consultar los procesos locales antes de actualizar MilyVoice.'
    }

    foreach ($process in $processes) {
        $rawPath = [string]$process.ExecutablePath
        if ([string]::IsNullOrWhiteSpace($rawPath)) { continue }
        try {
            $processPath = [System.IO.Path]::GetFullPath($rawPath)
        } catch {
            continue
        }
        $owned = $false
        foreach ($candidate in $ownedPaths) {
            if ([string]::Equals($processPath, $candidate, [System.StringComparison]::OrdinalIgnoreCase)) {
                $owned = $true
                break
            }
        }
        if (-not $owned) { continue }

        Write-Step "Cerrando proceso anterior de MilyVoice PID=$($process.ProcessId)."
        try {
            Stop-Process -Id ([int]$process.ProcessId) -Force -ErrorAction Stop
        } catch {
            throw 'RUNTIME_PROCESS_STOP_FAILED|No se pudo cerrar un proceso anterior de MilyVoice antes de actualizar.'
        }

        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            if (-not (Get-Process -Id ([int]$process.ProcessId) -ErrorAction SilentlyContinue)) { break }
            Start-Sleep -Milliseconds 100
        }
        if (Get-Process -Id ([int]$process.ProcessId) -ErrorAction SilentlyContinue) {
            throw 'RUNTIME_PROCESS_STOP_FAILED|Un proceso anterior de MilyVoice siguió activo y bloquea la actualización.'
        }
    }
}

function Resolve-UnstructuredFailure([string]$Stage) {
    switch ($Stage) {
        'COMPONENTS_CHECK' { return @('BOOTSTRAP_COMPONENT_CHECK_FAILED', 'No se pudieron validar los componentes incluidos.') }
        'RUNTIME_VERIFY' { return @('RUNTIME_VERIFY_FAILED', 'No se pudo verificar la integridad del runtime privado.') }
        'RUNTIME_EXTRACT' { return @('RUNTIME_EXTRACT_FAILED', 'No se pudo extraer el runtime privado incluido en el instalador.') }
        'RUNTIME_MANIFEST' { return @('RUNTIME_VERIFY_FAILED', 'No se pudo validar el manifiesto del runtime privado.') }
        'RUNTIME_IMPORT' { return @('RUNTIME_IMPORT_FAILED', 'El runtime privado no pudo cargar sus dependencias base.') }
        'RUNTIME_ACTIVATE' { return @('RUNTIME_ACTIVATE_FAILED', 'No se pudo activar el runtime privado en el perfil del usuario.') }
        'ENGINE_COPY' { return @('ENGINE_COPY_FAILED', 'No se pudo preparar el motor local incluido.') }
        'EXTENSION_COPY' { return @('EXTENSION_COPY_FAILED', 'No se pudo preparar la extensión Chromium incluida.') }
        'BRIDGE_COPY' { return @('BRIDGE_COPY_FAILED', 'No se pudo preparar el puente Native Messaging incluido.') }
        'NATIVE_REGISTER' { return @('NATIVE_HOST_REGISTER_FAILED', 'No se pudo registrar el puente con los navegadores Chromium.') }
        'ENGINE_DIAGNOSE' { return @('ENGINE_DIAGNOSE_FAILED', 'El motor incluido no pasó su diagnóstico local.') }
        'BOOTSTRAP_FINALIZE' { return @('BOOTSTRAP_FINALIZE_FAILED', 'La preparación local terminó, pero no pudo guardar su estado final.') }
        default { return @('BOOTSTRAP_FAILED', 'La preparación local no terminó correctamente.') }
    }
}

function Test-PythonModule([string]$Python, [string]$Module) {
    $probe = "import importlib; importlib.import_module('$Module')"
    & $Python -c $probe 1>$null 2>$null
    return $LASTEXITCODE -eq 0
}

try {
    Set-BootstrapStage 'COMPONENTS_CHECK' 'Verificando componentes incluidos.'
    foreach ($required in @(
        @{ Path = $RuntimeZip; Code = 'RUNTIME_ARCHIVE_MISSING' },
        @{ Path = $RuntimeHash; Code = 'RUNTIME_HASH_MISSING' },
        @{ Path = (Join-Path $EngineSource 'main.py'); Code = 'ENGINE_MISSING' },
        @{ Path = (Join-Path $EngineSource 'mily_ai\__init__.py'); Code = 'ENGINE_PACKAGE_MISSING' },
        @{ Path = (Join-Path $ExtensionSource 'manifest.json'); Code = 'EXTENSION_MISSING' },
        @{ Path = $BridgeSource; Code = 'BRIDGE_MISSING' },
        @{ Path = $RegisterScript; Code = 'BRIDGE_REGISTER_MISSING' },
        @{ Path = $NativeTemplate; Code = 'NATIVE_MANIFEST_MISSING' }
    )) {
        Assert-File $required.Path $required.Code
    }

    Set-BootstrapStage 'RUNTIME_VERIFY' 'Verificando integridad del runtime privado.'
    Write-Step 'Verificando runtime Python privado.'
    $expectedRuntimeHash = Read-ExpectedSha256 $RuntimeHash
    try {
        $actualRuntimeHash = Get-Sha256Hex $RuntimeZip
    } catch {
        throw 'RUNTIME_HASH_COMPUTE_FAILED|No se pudo calcular la firma SHA-256 del runtime incluido.'
    }
    if ($expectedRuntimeHash -ne $actualRuntimeHash) {
        throw 'RUNTIME_HASH_MISMATCH|El runtime incluido no pasó la verificación de integridad.'
    }

    New-Item -ItemType Directory -Force -Path $AppRoot,$RuntimeParent,$ConfigRoot,$CacheRoot,$ModelsRoot,$BridgeRoot | Out-Null

    Set-BootstrapStage 'RUNTIME_EXTRACT' 'Extrayendo runtime privado.'
    Expand-RuntimeArchive $RuntimeZip $RuntimeNext
    $nextPython = Join-Path $RuntimeNext 'python.exe'
    $runtimeManifestPath = Join-Path $RuntimeNext 'runtime-manifest.json'
    Assert-File $nextPython 'RUNTIME_PYTHON_MISSING'
    Assert-File $runtimeManifestPath 'RUNTIME_MANIFEST_MISSING'

    Set-BootstrapStage 'RUNTIME_MANIFEST' 'Validando manifiesto del runtime privado.'
    $runtimeManifest = Get-Content $runtimeManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    try {
        $pythonHash = Get-Sha256Hex $nextPython
    } catch {
        throw 'RUNTIME_PYTHON_HASH_COMPUTE_FAILED|No se pudo calcular la firma SHA-256 del Python privado.'
    }
    $manifestPythonHash = ([string]$runtimeManifest.pythonSha256).Trim().ToLowerInvariant()
    if ($manifestPythonHash -notmatch '^[0-9a-f]{64}$') {
        throw 'RUNTIME_MANIFEST_INVALID|El manifiesto del runtime contiene una firma de Python inválida.'
    }
    if ($pythonHash -ne $manifestPythonHash) {
        throw 'RUNTIME_PYTHON_HASH_MISMATCH|python.exe no coincide con el manifiesto del runtime.'
    }

    # El manifest generado en build es la única fuente del contrato de módulos.
    # El fallback conserva compatibilidad con runtimes 2.0.1 previos a schema v3.
    $requiredRuntimeModules = @()
    $optionalRuntimeModules = @()
    try { $requiredRuntimeModules = @($runtimeManifest.requiredModules) } catch { $requiredRuntimeModules = @() }
    try { $optionalRuntimeModules = @($runtimeManifest.optionalModules) } catch { $optionalRuntimeModules = @() }
    $requiredRuntimeModules = @($requiredRuntimeModules | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ })
    $optionalRuntimeModules = @($optionalRuntimeModules | ForEach-Object { ([string]$_).Trim() } | Where-Object { $_ })
    if ($requiredRuntimeModules.Count -eq 0) { $requiredRuntimeModules = @($DefaultRequiredRuntimeModules) }
    if ($optionalRuntimeModules.Count -eq 0) { $optionalRuntimeModules = @($DefaultOptionalRuntimeModules) }

    Set-BootstrapStage 'RUNTIME_IMPORT' 'Comprobando dependencias base del runtime privado.'
    $missingRequired = @()
    foreach ($module in $requiredRuntimeModules) {
        if (-not (Test-PythonModule $nextPython $module)) {
            $missingRequired += $module
        }
    }
    if ($missingRequired.Count -gt 0) {
        throw ('RUNTIME_IMPORT_FAILED|No se pudo cargar el runtime base requerido: {0}.' -f ($missingRequired -join ', '))
    }

    # Los adapters opcionales se diagnostican, pero jamás bloquean la instalación.
    $script:OptionalRuntimeUnavailable = @()
    foreach ($module in $optionalRuntimeModules) {
        if (-not (Test-PythonModule $nextPython $module)) {
            $script:OptionalRuntimeUnavailable += $module
        }
    }
    if ($script:OptionalRuntimeUnavailable.Count -gt 0) {
        Write-Step ('Motores opcionales no disponibles en este equipo: {0}. Se usará fallback.' -f ($script:OptionalRuntimeUnavailable -join ', '))
    }

    Set-BootstrapStage 'RUNTIME_ACTIVATE' 'Activando runtime privado.'
    Write-Step 'Activando runtime y motor.'
    Stop-MilyVoiceOwnedProcesses
    if (Test-Path $RuntimeRoot) { Remove-Item $RuntimeRoot -Recurse -Force }
    Move-Item -LiteralPath $RuntimeNext -Destination $RuntimeRoot

    Set-BootstrapStage 'ENGINE_COPY' 'Preparando motor local.'
    if (Test-Path $EngineApp) { Remove-Item $EngineApp -Recurse -Force }
    Copy-DirectoryContents $EngineSource $EngineApp 'ENGINE_COPY_FAILED'
    Assert-File (Join-Path $EngineApp 'main.py') 'ENGINE_MAIN_COPY_FAILED'
    Assert-File (Join-Path $EngineApp 'mily_ai\__init__.py') 'ENGINE_PACKAGE_COPY_FAILED'
    Remove-Item (Join-Path $EngineApp 'mily_ai\__pycache__') -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $EngineApp 'tests\__pycache__') -Recurse -Force -ErrorAction SilentlyContinue

    Set-BootstrapStage 'EXTENSION_COPY' 'Preparando extensión Chromium.'
    Write-Step 'Instalando extensión y puente local.'
    if (Test-Path $ExtensionRoot) { Remove-Item $ExtensionRoot -Recurse -Force }
    Copy-DirectoryContents $ExtensionSource $ExtensionRoot 'EXTENSION_COPY_FAILED'
    Assert-File (Join-Path $ExtensionRoot 'manifest.json') 'EXTENSION_MANIFEST_COPY_FAILED'

    Set-BootstrapStage 'BRIDGE_COPY' 'Preparando puente Native Messaging.'
    Copy-Item -LiteralPath $BridgeSource -Destination $BridgeTarget -Force

    Set-BootstrapStage 'NATIVE_REGISTER' 'Registrando puente Native Messaging.'
    & $RegisterScript -BridgePath $BridgeTarget -ManifestTemplate $NativeTemplate -ManifestOutput $NativeManifest
    if ($LASTEXITCODE -ne 0) {
        throw 'NATIVE_HOST_REGISTER_FAILED|No se pudo registrar el puente con los navegadores Chromium.'
    }

    Set-BootstrapStage 'ENGINE_DIAGNOSE' 'Ejecutando diagnóstico local del motor.'
    Write-Step 'Ejecutando diagnóstico local.'
    $embeddedPython = Join-Path $RuntimeRoot 'python.exe'
    & $embeddedPython (Join-Path $EngineApp 'main.py') diagnose `
        --data-dir $AppRoot `
        --config-dir $ConfigRoot `
        --cache-dir $CacheRoot `
        --models-dir $ModelsRoot
    if ($LASTEXITCODE -ne 0) {
        throw 'ENGINE_DIAGNOSE_FAILED|El motor incluido no pasó su diagnóstico local.'
    }

    $script:BootstrapStage = 'BOOTSTRAP_FINALIZE'
    $modelState = if (Test-Path (Join-Path $ModelsRoot 'current.json')) { 'ready' } else { 'model-pending' }
    $message = if ($modelState -eq 'ready') {
        'Runtime, motor, extensión y bridge preparados.'
    } else {
        'Runtime, motor, extensión y bridge preparados. El modelo se descargará desde la aplicación.'
    }
    Write-BootstrapStatus $modelState 'BOOTSTRAP_OK' $message
    Write-Step 'Preparación local completada sin depender de Python del sistema.'
    exit 0
} catch {
    $raw = [string]$_.Exception.Message
    $parts = $raw.Split('|', 2)
    if ($parts.Count -eq 2) {
        $code = $parts[0]
        $message = $parts[1]
    } else {
        $resolved = Resolve-UnstructuredFailure $script:BootstrapStage
        $code = $resolved[0]
        $message = $resolved[1]
    }
    try {
        Write-BootstrapStatus 'failed' $code $message
    } catch {
        # El error original debe seguir visible aunque no podamos escribir status.json.
    }
    Write-Error ('{0}: {1}' -f $code, $message)
    exit 1
}
