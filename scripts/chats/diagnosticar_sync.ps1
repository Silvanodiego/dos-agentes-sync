$ErrorActionPreference = 'Continue'
Write-Output ('PC: ' + $env:COMPUTERNAME + ' / ' + $env:USERNAME)
$local = Join-Path $env:LOCALAPPDATA 'CodexSync'
foreach ($name in @('activation-status.json', 'live-sync-status.json')) {
    Write-Output ('--- ' + $name + ' ---')
    $path = Join-Path $local $name
    if (Test-Path -LiteralPath $path) { Get-Content -LiteralPath $path } else { Write-Output 'NO EXISTE' }
}
Write-Output '--- Tareas ---'
Get-ScheduledTask -TaskName 'CodexChats*' -ErrorAction SilentlyContinue | ForEach-Object {
    $info = $_ | Get-ScheduledTaskInfo
    Write-Output ($_.TaskName + ' / ' + $_.State + ' / resultado=' + $info.LastTaskResult + ' / ultima=' + $info.LastRunTime)
}
Write-Output '--- Bases nativas (solo nombres; no contenido) ---'
foreach ($pattern in @('state_*.sqlite', 'thread_history_*.sqlite')) {
    Get-ChildItem -LiteralPath (Join-Path $env:USERPROFILE '.codex') -Filter $pattern -File -ErrorAction SilentlyContinue | Select-Object Name, Length | Format-Table -AutoSize
}
Write-Output '--- Drive: manifiestos detectados ---'
foreach ($drive in Get-PSDrive -PSProvider FileSystem) {
    foreach ($folder in @('Mi unidad', 'My Drive')) {
        $path = Join-Path $drive.Root ($folder + '\CodexSync\live-v1\machines')
        if (Test-Path -LiteralPath $path) {
            Write-Output $path
            Get-ChildItem -LiteralPath $path -Filter '*.json' -File | Select-Object Name, LastWriteTime | Format-Table -AutoSize
        }
    }
}
