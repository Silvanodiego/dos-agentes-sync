#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'CodexSync'),
    [string]$PythonExecutable = 'C:\dos_agentes_local\.venv\Scripts\pythonw.exe',
    [string]$Acceptance = ''
)
$ErrorActionPreference = 'Stop'
$worker = Join-Path $PSScriptRoot 'sync_chats_cerrado.py'
foreach ($file in @($PythonExecutable, $worker, (Join-Path $InstallRoot 'codexsync.toml'))) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Falta $file" }
}
$arguments = '"' + $worker + '" --install-root "' + $InstallRoot + '"'
if ($Acceptance) {
    if (-not (Test-Path -LiteralPath $Acceptance -PathType Leaf)) { throw 'Falta la recuperacion verificada' }
    $arguments += ' --acceptance "' + $Acceptance + '"'
}
$action = New-ScheduledTaskAction -Execute $PythonExecutable -Argument $arguments -WorkingDirectory $PSScriptRoot
$periodic = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 10)
$login = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName 'CodexChatsSyncCold' -Action $action -Trigger @($periodic, $login) -Principal $principal -Settings $settings -Description 'Sincroniza sesiones sin credenciales, solo con Codex cerrado. Conserva divergencias y nunca cierra la app.' -Force | Out-Null
Start-ScheduledTask -TaskName 'CodexChatsSyncCold'
Write-Output 'CodexChatsSyncCold registrada: inicio de sesion y cada 10 minutos; espera mientras Codex esta abierto.'
