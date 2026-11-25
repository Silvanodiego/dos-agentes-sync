# Runs from an extracted, versioned payload, independent of the dirty Git checkout.
param([string]$Repo = 'C:\dos_agentes_local')
$ErrorActionPreference = 'Stop'
$pythonw = Join-Path $Repo '.venv\Scripts\pythonw.exe'
if (!(Test-Path -LiteralPath $pythonw -PathType Leaf)) { throw "Falta Python instalado: $pythonw" }
$runner = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$local = Join-Path $env:LOCALAPPDATA 'CodexSync'
New-Item -ItemType Directory -Path $local -Force | Out-Null
# Save previous task definitions for rollback without deleting or stopping Codex.
$backups = Join-Path $local ('task-backups\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backups -Force | Out-Null
foreach ($name in @('CodexChatsSyncLive','CodexChatsAutoSetup','CodexChatsSyncCold')) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Export-ScheduledTask -TaskName $name | Set-Content -LiteralPath (Join-Path $backups ($name + '.xml')) -Encoding Unicode
    }
}
Write-Host 'Activando adaptador de chats aislado; no se ejecuta git pull ni se cambian archivos del repositorio.'
& (Join-Path $PSScriptRoot 'registrar_activacion_automatica.ps1') -Root $runner -PythonExecutable $pythonw
& (Join-Path $PSScriptRoot 'diagnosticar_sync.ps1')
$activationPath = Join-Path $local 'activation-status.json'
if (!(Test-Path -LiteralPath $activationPath)) { throw 'No se genero el estado de activacion.' }
$activation = Get-Content -LiteralPath $activationPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($activation.status -ne 'activated') {
    throw ('Activacion pendiente; no se anuncia exito. Detalle: ' + $activation.detail)
}
Write-Host 'Primera sincronizacion verificada. Los chats nuevos se revisan automaticamente cada 2 minutos.'
