[CmdletBinding()]
param(
    [switch]$Staged,
    [string]$Ruta = "."
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
$previousLocks = $env:GIT_OPTIONAL_LOCKS
$env:GIT_OPTIONAL_LOCKS = '0'

try {
    Push-Location -LiteralPath 'C:\dos_agentes_local'
    try {
        # Use native Git, bypassing the workspace git.cmd adapter.
        $gitCommand = Get-Command git.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1
        $gitPath = $gitCommand.Source
        $gitBase = @('-c', 'core.bare=false', '--no-pager')

        & $gitPath @gitBase status -sb
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        $diffArgs = @('diff')
        if ($Staged) { $diffArgs += '--cached' }
        $statArgs = $diffArgs + @('--stat')
        & $gitPath @gitBase @statArgs
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

        $pathArgs = $diffArgs + @('--', $Ruta)
        $diffLines = @(& $gitPath @gitBase @pathArgs)
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        if ($diffLines.Count -eq 0) {
            Write-Output '[OK] Sin diferencias para auditar.'
        } else {
            $diffLines | Write-Output
        }
    } finally {
        Pop-Location
    }
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
} finally {
    $env:GIT_OPTIONAL_LOCKS = $previousLocks
}
