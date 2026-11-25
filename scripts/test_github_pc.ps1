$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'github_pc.ps1')
function Winget { throw 'No debe instalar GitHub CLI en esta prueba.' }
function gh.exe {
    $script:commands += ,@($args)
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'auth' -and $args[1] -eq 'status' -and !$script:authenticated) { $global:LASTEXITCODE = 1 }
    if ($args[0] -eq 'auth' -and $args[1] -eq 'login') {
        if ($script:loginFails) { $global:LASTEXITCODE = 1 } else { $script:authenticated = $true }
    }
    if ($args[0] -eq 'api') { if ($script:permission) { 'true' } else { 'false' } }
}
function Run([string]$exe,[string[]]$Arguments) {
    & $exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Fallo de autenticacion simulado.' }
}
foreach ($case in @('authenticated','login','forbidden','failed-login')) {
    $script:commands = @()
    $script:authenticated = $case -in @('authenticated','forbidden')
    $script:permission = $case -ne 'forbidden'
    $script:loginFails = $case -eq 'failed-login'
    $failed = $false
    try { Ensure-GitHubAccess } catch { $failed = $true }
    if ($failed -ne ($case -in @('forbidden','failed-login'))) { throw "Resultado incorrecto: $case" }
    $logins = @($script:commands | Where-Object { $_[0] -eq 'auth' -and $_[1] -eq 'login' })
    $expectedLogins = if ($case -in @('login','failed-login')) { 1 } else { 0 }
    if ($logins.Count -ne $expectedLogins) { throw "Login innecesario o ausente: $case" }
}
Write-Host 'OK: sesion existente, login web requerido, permiso denegado y login fallido.'
