#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$CloudRoot = '',
    [string]$MachineId = ($env:COMPUTERNAME + '-' + $env:USERNAME),
    [string]$CodexHome = (Join-Path $env:USERPROFILE '.codex'),
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'CodexSync'),
    [string]$PythonExecutable = 'C:\dos_agentes_local\.venv\Scripts\pythonw.exe'
)
$ErrorActionPreference = 'Stop'
if (-not $CloudRoot) {
    $candidates = @(
        foreach ($drive in Get-PSDrive -PSProvider FileSystem) {
            foreach ($folder in @('Mi unidad', 'My Drive')) {
                $candidate = Join-Path $drive.Root ($folder + '\CodexSync\live-v1')
                if (Test-Path -LiteralPath (Join-Path $candidate 'machines') -PathType Container) { $candidate }
            }
        }
    ) | Select-Object -Unique
    if (@($candidates).Count -ne 1) {
        throw 'No se encuentra una unica carpeta compartida CodexSync/live-v1. Inicie Drive o especifique -CloudRoot con su ruta.'
    }
    $CloudRoot = @($candidates)[0]
}
$MachineId = $MachineId -replace '[^A-Za-z0-9_-]', '-'
if ($MachineId.Length -gt 40) { throw 'MachineId debe tener como maximo 40 caracteres' }
$worker = Join-Path $PSScriptRoot 'sync_chats_abierto.py'
foreach ($file in @($worker, $PythonExecutable)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Falta $file" }
}
foreach ($module in @('proyectos_portables.py', 'continuidad_chats.py', 'rutas_historial.py', 'backup_chats.py', 'coverage_chats.py')) {
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot $module) -PathType Leaf)) { throw "Falta el modulo $module; actualice el repositorio completo" }
}
foreach ($pattern in @('state_*.sqlite', 'thread_history_*.sqlite')) {
    if (@(Get-ChildItem -LiteralPath $CodexHome -Filter $pattern -File).Count -ne 1) {
        throw "Falta la base nativa unica $pattern en $CodexHome; abrir Codex e iniciar un chat primero"
    }
}
New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
$state = Join-Path $InstallRoot ('live-state-' + $MachineId + '.json')
$arguments = '"' + $worker + '" --home "' + $CodexHome + '" --cloud "' + $CloudRoot + '" --machine "' + $MachineId + '" --state "' + $state + '"'
$action = New-ScheduledTaskAction -Execute $PythonExecutable -Argument $arguments -WorkingDirectory $PSScriptRoot
$periodic = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 2)
$login = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName 'CodexChatsSyncLive' -Action $action -Trigger @($periodic, $login) -Principal $principal -Settings $settings -Description 'Replica chats con Codex abierto mediante snapshots SQLite; nunca reemplaza conversaciones existentes.' -Force | Out-Null
# Preserve the cold setup as a disabled fallback; never run both workers.
$cold = Get-ScheduledTask -TaskName 'CodexChatsSyncCold' -ErrorAction SilentlyContinue
if ($cold) { Disable-ScheduledTask -TaskName 'CodexChatsSyncCold' | Out-Null }
Start-ScheduledTask -TaskName 'CodexChatsSyncLive'
Write-Output ('CodexChatsSyncLive activa: ' + $MachineId + ', cada 2 minutos y al iniciar sesion; Codex puede seguir abierto.')
