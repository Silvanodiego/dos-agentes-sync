param([ValidateSet('startup','periodic')][string]$Mode = 'periodic')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$local = Join-Path $root '.sync-local'
New-Item -ItemType Directory -Force -Path $local | Out-Null
try {
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (!(Test-Path -LiteralPath $python)) {
        $py = Get-Command py.exe -ErrorAction SilentlyContinue
        if (!$py) { throw 'Instalar Python 3 y su lanzador py antes del primer arranque.' }
        & $py.Source -3 -m venv (Join-Path $root '.venv') >> (Join-Path $local 'bootstrap.log') 2>&1
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear .venv.' }
    }
    & $python -X utf8 (Join-Path $PSScriptRoot 'sync_git.py') $Mode >> (Join-Path $local 'launcher.log') 2>&1
    exit $LASTEXITCODE
} catch {
    Add-Content -LiteralPath (Join-Path $local 'launcher.log') -Value "$(Get-Date -Format s) ERROR $_"
    exit 1
}
