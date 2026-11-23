$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$local = Join-Path $root '.sync-local\backups'
New-Item -ItemType Directory -Force -Path $local | Out-Null
$runPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$previous = Get-ItemProperty -LiteralPath $runPath
$previous | Select-Object DosAgentesPanel8787,DosAgentesBridge8765,DosAgentesSync |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $local 'run-original.json')

$script = Join-Path $PSScriptRoot 'sync_silencioso.vbs'
$wscript = Join-Path $env:WINDIR 'System32\wscript.exe'
$action = New-ScheduledTaskAction -Execute $wscript -Argument ('//B //Nologo "' + $script + '" periodic') -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 10)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -Hidden -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 8)
Register-ScheduledTask -TaskName 'DosAgentesGitSync' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Commit, pull rebase y push cada 10 minutos; aplica reglas compartidas sin ventana.' -Force | Out-Null

New-ItemProperty -LiteralPath $runPath -Name 'DosAgentesSync' -PropertyType String -Value ('"' + $wscript + '" //B //Nologo "' + $script + '" startup') -Force | Out-Null
foreach ($name in @('DosAgentesPanel8787','DosAgentesBridge8765')) {
    if ($previous.PSObject.Properties.Name -contains $name) {
        Remove-ItemProperty -LiteralPath $runPath -Name $name
    }
}
$shortcut = Join-Path ([Environment]::GetFolderPath('Startup')) 'Codex - Monitor cuota.lnk'
if (Test-Path -LiteralPath $shortcut) {
    Move-Item -LiteralPath $shortcut -Destination (Join-Path $local 'Monitor-cuota-arranque-anterior.lnk') -Force
}
Write-Output 'DosAgentesGitSync activa cada 10 minutos; DosAgentesSync registrado al iniciar sesion.'
