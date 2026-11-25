# Chequeos pasivos locales: no inicia servicios ni envia prompts.
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$ErrorActionPreference = 'Stop'
$failures = New-Object 'System.Collections.Generic.List[string]'

function Test-LocalTcp([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    $pending = $null
    try {
        $pending = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $pending.AsyncWaitHandle.WaitOne(4000)) { throw 'timeout de 4 s' }
        $client.EndConnect($pending)
    } finally {
        if ($null -ne $pending) { $pending.AsyncWaitHandle.Close() }
        $client.Close()
    }
}

foreach ($port in @(8765, 8045)) {
    try { Test-LocalTcp $port }
    catch { $failures.Add("TCP ${port}: no responde dentro de 4 s o conexion rechazada") }
}

$http = $null
$handler = $null
try {
    Add-Type -AssemblyName System.Net.Http
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.UseProxy = $false
    $handler.AllowAutoRedirect = $false
    $http = New-Object System.Net.Http.HttpClient($handler)
    $http.Timeout = [TimeSpan]::FromSeconds(4)
    $json = $http.GetStringAsync('http://127.0.0.1:9222/json/list').GetAwaiter().GetResult()
    $tabs = @($json | ConvertFrom-Json)
    $geminiTabs = @($tabs | Where-Object {
        if ($_.type -ne 'page') { return $false }
        $url = $null
        [Uri]::TryCreate([string]$_.url, [UriKind]::Absolute, [ref]$url) -and
            $url.Host -eq 'gemini.google.com'
    })
    if ($geminiTabs.Count -eq 0) { $failures.Add('CDP 9222: responde, pero no hay pestanas de gemini.google.com') }
} catch {
    $failures.Add('CDP 9222 /json/list: fallo HTTP, JSON invalido o timeout de 4 s')
} finally {
    if ($null -ne $http) { $http.Dispose() }
    if ($null -ne $handler) { $handler.Dispose() }
}

if ($failures.Count -gt 0 -and [Environment]::UserInteractive -and
    [System.Diagnostics.Process]::GetCurrentProcess().SessionId -ne 0) {
    $icon = $null
    try {
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        $icon = New-Object System.Windows.Forms.NotifyIcon
        $icon.Icon = [System.Drawing.SystemIcons]::Warning
        $icon.Visible = $true
        $icon.ShowBalloonTip(2000, 'Dos Agentes: verificacion', ($failures -join '; '),
            [System.Windows.Forms.ToolTipIcon]::Warning)
        $until = [DateTime]::UtcNow.AddSeconds(2)
        while ([DateTime]::UtcNow -lt $until) {
            [System.Windows.Forms.Application]::DoEvents()
            Start-Sleep -Milliseconds 100
        }
    } catch {
        # El detalle de los fallos queda siempre registrado, incluso sin UI.
    } finally {
        if ($null -ne $icon) { $icon.Visible = $false; $icon.Dispose() }
    }
}

try {
    $root = Split-Path -Parent $PSScriptRoot
    $logDir = Join-Path $root 'logs'
    $null = [IO.Directory]::CreateDirectory($logDir)
    $logPath = Join-Path $logDir 'verificador_10m.log'
    $status = if ($failures.Count -eq 0) { 'OK' } else { 'FALLO: ' + ($failures -join '; ') }
    $line = [DateTimeOffset]::Now.ToString('yyyy-MM-dd HH:mm:ss zzz') + ' ' + $status
    $utf8 = [System.Text.UTF8Encoding]::new($false)
    $previous = @()
    if ([IO.File]::Exists($logPath)) { $previous = @(Get-Content -LiteralPath $logPath -Encoding UTF8 -Tail 199) }
    [IO.File]::WriteAllLines($logPath, [string[]]($previous + @($line)), $utf8)
} catch {
    [Console]::Error.WriteLine('FALLO: no se pudo escribir logs\verificador_10m.log')
    exit 1
}
if ($failures.Count -gt 0) { exit 1 }
exit 0
