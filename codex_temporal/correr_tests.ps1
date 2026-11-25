[CmdletBinding()]
param([string]$Objetivo = "")

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

try {
    Push-Location -LiteralPath 'C:\dos_agentes_local'
    try {
        if ([string]::IsNullOrWhiteSpace($Objetivo)) {
            Write-Output 'Tests disponibles en la raiz y en scripts\:'
            foreach ($directory in @('C:\dos_agentes_local', 'C:\dos_agentes_local\scripts')) {
                if (Test-Path -LiteralPath $directory -PathType Container) {
                    Get-ChildItem -LiteralPath $directory -Filter 'test_*.py' -File |
                        Sort-Object Name | ForEach-Object { Write-Output $_.FullName }
                }
            }
            Write-Output 'No se ejecuto ninguna suite.'
            Write-Output 'Uso: powershell -NoProfile -ExecutionPolicy Bypass -File C:\dos_agentes_local\codex_temporal\correr_tests.ps1 -Objetivo scripts\test_rotacion_cuota.py'
            exit 0
        }

        $pythonPath = 'C:\dos_agentes_local\.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
            $pythonPath = (Get-Command python -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
        }
        & $pythonPath -m pytest -q $Objetivo
        exit $LASTEXITCODE
    } finally {
        Pop-Location
    }
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
