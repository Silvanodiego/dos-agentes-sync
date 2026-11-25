# Recuperacion local acotada, sin prompts ni credenciales.
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Add-Type -AssemblyName System.Net.Http
$handler = New-Object System.Net.Http.HttpClientHandler
$handler.UseProxy = $false
$handler.AllowAutoRedirect = $false
$http = New-Object System.Net.Http.HttpClient($handler)
$http.Timeout = [TimeSpan]::FromSeconds(4)

function Test-Tcp([int]$Port, [int]$Millis) {
    $client = New-Object System.Net.Sockets.TcpClient
    $pending = $null
    try {
        $pending = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $pending.AsyncWaitHandle.WaitOne([Math]::Max(1,$Millis))) { return $false }
        $client.EndConnect($pending)
        return $true
    } catch { return $false }
    finally {
        if ($null -ne $pending) { $pending.AsyncWaitHandle.Close() }
        $client.Close()
    }
}
function Get-Health([int]$BudgetMs = 12000) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $state = @{ Manager=$false; Bridge=$false; CdpAlive=$false; Gemini=$false }
    $state.Manager = Test-Tcp 8045 ([Math]::Min(4000,[Math]::Max(1,$BudgetMs-$watch.ElapsedMilliseconds)))
    $state.Bridge = Test-Tcp 8765 ([Math]::Min(4000,[Math]::Max(1,$BudgetMs-$watch.ElapsedMilliseconds)))
    $cancel = New-Object System.Threading.CancellationTokenSource
    try {
        $cancel.CancelAfter([int][Math]::Min(4000,[Math]::Max(1,$BudgetMs-$watch.ElapsedMilliseconds)))
        $response = $http.GetAsync('http://127.0.0.1:9222/json/list', $cancel.Token).GetAwaiter().GetResult()
        try {
            $null = $response.EnsureSuccessStatusCode()
            $tabs = @($response.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json)
            $state.CdpAlive = $true
            foreach ($tab in $tabs) {
                $url = $null
                if ($tab.type -eq 'page' -and [Uri]::TryCreate([string]$tab.url,[UriKind]::Absolute,[ref]$url) -and $url.Host -eq 'gemini.google.com') { $state.Gemini = $true }
            }
        } finally { $response.Dispose() }
    } catch { }
    finally { $cancel.Dispose() }
    return $state
}
function Health-Detail($state) {
    $details = @()
    if (-not $state.Manager) { $details += '8045 no responde' }
    if (-not $state.Bridge) { $details += '8765 no responde' }
    if (-not $state.CdpAlive) { $details += '9222 /json/list no responde' }
    elseif (-not $state.Gemini) { $details += '9222 sin pestana Gemini' }
    return ($details -join '; ')
}
$actions = New-Object 'System.Collections.Generic.List[string]'
$status = 'FALLO_PERSISTENTE: error interno del verificador'
$exitCode = 1
try {
    $initial = Get-Health
    if (-not (Health-Detail $initial)) { $status = 'OK'; $exitCode = 0 }
    else {
        # Si no puede inspeccionar procesos, no arriesga iniciar duplicados.
        $processes = @(Get-CimInstance Win32_Process -ErrorAction Stop)
        if (-not $initial.Manager) {
            $existing = @($processes | Where-Object { $_.Name -eq 'antigravity-manager.exe' })
            if ($existing.Count) { $actions.Add('8045 proceso existente; no se duplica') }
            else {
                try {
                    $null = Start-Process -FilePath (Join-Path $root 'AntigravityManager\antigravity-manager.exe') -WorkingDirectory (Join-Path $root 'AntigravityManager') -WindowStyle Hidden -PassThru
                    $actions.Add('inicio Manager solicitado')
                } catch { $actions.Add('no se pudo iniciar Manager') }
            }
        }
        if (-not $initial.Bridge) {
            $existing = @($processes | Where-Object { $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -match '(^|[\\/\s"])bridge_server\.py(["\s]|$)' })
            if ($existing.Count) { $actions.Add('8765 proceso existente; no se duplica') }
            else {
                try {
                    $null = Start-Process -FilePath (Join-Path $root '.venv\Scripts\python.exe') -ArgumentList ('"' + (Join-Path $root 'bridge_server.py') + '"') -WorkingDirectory $root -WindowStyle Hidden -PassThru
                    $actions.Add('inicio 8765 solicitado')
                } catch { $actions.Add('no se pudo iniciar 8765') }
            }
        }
        if (-not $initial.Gemini) {
            if ($initial.CdpAlive) {
                try {
                    $url = 'http://127.0.0.1:9222/json/new?' + [Uri]::EscapeDataString('https://gemini.google.com/app')
                    $response = $http.PutAsync($url, [System.Net.Http.HttpContent]$null).GetAwaiter().GetResult()
                    try { $null = $response.EnsureSuccessStatusCode() } finally { $response.Dispose() }
                    $actions.Add('pestana Gemini abierta via CDP')
                } catch { $actions.Add('no se pudo abrir pestana Gemini via CDP') }
            } else {
                $existing = @($processes | Where-Object { $_.Name -match '^(chrome|msedge)\.exe$' -and ($_.CommandLine -match '--remote-debugging-port[=\s]+9222' -or $_.CommandLine -match 'chrome_gemini_profile') })
                if ($existing.Count) { $actions.Add('9222 navegador existente; no se duplica') }
                else {
                    try {
                        $launcher = Join-Path $root 'abrir_chrome_gemini_oculto.bat'
                        $null = Start-Process -FilePath $env:ComSpec -ArgumentList ('/d /c ""' + $launcher + '""') -WorkingDirectory $root -WindowStyle Hidden -PassThru
                        $actions.Add('inicio Chrome oculto solicitado')
                    } catch { $actions.Add('no se pudo iniciar Chrome oculto') }
                }
            }
        }
        $wait = [Diagnostics.Stopwatch]::StartNew()
        do {
            $final = Get-Health ([int][Math]::Max(1,10000-$wait.ElapsedMilliseconds))
            if (-not (Health-Detail $final)) { break }
            if ($wait.ElapsedMilliseconds -ge 10000) { break }
            Start-Sleep -Milliseconds ([int][Math]::Min(250,10000-$wait.ElapsedMilliseconds))
        } while ($wait.ElapsedMilliseconds -lt 10000)
        $detail = Health-Detail $final
        if ($detail) { $status = 'FALLO_PERSISTENTE: ' + $detail + '; ' + ($actions -join '; ') }
        else { $status = 'RECUPERADO: ' + ($actions -join '; '); $exitCode = 0 }
    }
} catch { $status = 'FALLO_PERSISTENTE: no se pudo inspeccionar o recuperar servicios; ' + ($actions -join '; ') }
finally { $http.Dispose(); $handler.Dispose() }

if ($exitCode -ne 0 -and [Environment]::UserInteractive -and [Diagnostics.Process]::GetCurrentProcess().SessionId -ne 0) {
    $icon = $null
    try {
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        $icon = New-Object System.Windows.Forms.NotifyIcon
        $icon.Icon = [Drawing.SystemIcons]::Warning
        $icon.Visible = $true
        $icon.ShowBalloonTip(2000,'Dos Agentes: verificacion',$status,[Windows.Forms.ToolTipIcon]::Warning)
        $until = [DateTime]::UtcNow.AddSeconds(2)
        while ([DateTime]::UtcNow -lt $until) { [Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 100 }
    } catch { }
    finally { if ($null -ne $icon) { $icon.Visible=$false; $icon.Dispose() } }
}
try {
    $logDir = Join-Path $root 'logs'
    $null = [IO.Directory]::CreateDirectory($logDir)
    $logPath = Join-Path $logDir 'verificador_10m.log'
    $previous = @()
    if (Test-Path -LiteralPath $logPath) { $previous = @(Get-Content -LiteralPath $logPath -Encoding UTF8 -Tail 199) }
    $line = [DateTimeOffset]::Now.ToString('yyyy-MM-dd HH:mm:ss zzz') + ' ' + $status
    [IO.File]::WriteAllLines($logPath,[string[]]($previous+@($line)),[Text.UTF8Encoding]::new($false))
} catch { [Console]::Error.WriteLine('FALLO_PERSISTENTE: no se pudo escribir el log'); exit 1 }
exit $exitCode
