[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$env:PYTHONPATH = Join-Path $Root 'services\ai'

@'
from pathlib import Path
from mily_ai.models import ModelCatalog
from mily_ai.resource_governor import ResourceGovernor, ResourceLimits

catalog = ModelCatalog(Path('unused'))
definition = catalog.definition('realtime-m2m100')
governor = ResourceGovernor(ResourceLimits())
decision = governor.preflight_model(
    model_ram_mb=float(definition['ramMb']),
    dedicated_vram_mb=float(definition['vramMb']),
    shared_gpu_mb=float(definition.get('sharedGpuMb', 0)),
)

print('QUALITY_PACK', definition['id'])
print('QUALITY_DECLARED_RAM_MB', definition['ramMb'])
print('QUALITY_DECLARED_VRAM_MB', definition['vramMb'])
print('QUALITY_ALLOWED_UNDER_2_GIB', decision.allowed)
print('QUALITY_REJECTION', decision.reason)

if decision.allowed:
    raise SystemExit('QUALITY_PACK_MUST_NOT_ACTIVATE_UNDER_2_GIB')
if decision.reason != 'PROCESS_MEMORY_LIMIT':
    raise SystemExit('QUALITY_PACK_EXPECTED_PROCESS_MEMORY_LIMIT')
print('QUALITY_PACK_POLICY_OK')
'@ | python -

if ($LASTEXITCODE -ne 0) { throw 'La política Quality/Lite no pasó.' }
