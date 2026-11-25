param([Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference = 'Stop'
$pythonw = Join-Path $Root '.venv\Scripts\pythonw.exe'
$worker = Join-Path $Root 'scripts\chats\activar_cuando_listo.py'
foreach ($file in @($pythonw,$worker)) { if (!(Test-Path -LiteralPath $file)) { throw "Falta $file" } }
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $pythonw -Argument ('"' + $worker + '" --root "' + $Root + '"') -WorkingDirectory $Root
$periodic = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 2)
$login = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -Hidden -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
Register-ScheduledTask -TaskName 'CodexChatsAutoSetup' -Action $action -Trigger @($periodic,$login) -Principal $principal -Settings $settings -Description 'Activa la replica de chats cuando Drive y Codex estan listos; sin cerrar Codex.' -Force | Out-Null
& (Join-Path $Root '.venv\Scripts\python.exe') $worker --root $Root
if ($LASTEXITCODE -ne 0) { throw 'No se pudo iniciar el activador de chats.' }
Write-Host 'Chats: activacion automatica registrada. Estado: %LOCALAPPDATA%\CodexSync\activation-status.json; si esta pending falta Drive o iniciar un chat en Codex.'
