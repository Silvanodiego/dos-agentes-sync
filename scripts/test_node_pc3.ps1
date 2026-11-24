param([Parameter(Mandatory=$true)][string]$Archive)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'node_pc3.ps1')
$repository = Split-Path $PSScriptRoot -Parent
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('node pc3 test ' + [guid]::NewGuid())
$installers = Join-Path $testRoot 'runtime\installers'
New-Item -ItemType Directory -Path $installers -Force | Out-Null
Copy-Item -LiteralPath $Archive -Destination (Join-Path $installers 'node-v24.22.3-win-x64.zip')
$oldPath = $env:Path
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
try {
    # Simula PC sin Node, sin alterar instalaciones ni PATH persistente de PC1.
    $env:Path = "$env:WINDIR\System32;$env:WINDIR"
    $local = Join-Path $testRoot 'runtime\node-v24.22.3-win-x64'
    New-Item -ItemType Directory -Path $local | Out-Null
    Set-Content -LiteralPath (Join-Path $local 'intento_anterior.txt') -Value 'conservar'
    Install-Node24 -Root $testRoot
    $backups = @(Get-ChildItem (Join-Path $testRoot 'runtime') -Directory -Filter '*.incompleto-*')
    if ($backups.Count -ne 1 -or !(Test-Path (Join-Path $backups[0].FullName 'intento_anterior.txt'))) { throw 'No se conservo el intento incompleto.' }
    $local = Join-Path $testRoot 'runtime\node-v24.22.3-win-x64'
    if ((Get-Command node.exe).Source -ne (Join-Path $local 'node.exe')) { throw 'No se selecciono el Node instalado.' }
    if (!(Test-Node24 -Directory $local)) { throw 'Node/npm/npx no funcionan.' }
    Install-Node24 -Root $testRoot  # Reutilizacion sin sobrescribir.
    $tokens = $null; $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot 'instalar_pc3.ps1'), [ref]$tokens, [ref]$errors)
    if ($errors.Count) { throw ($errors | Out-String) }
    $definition = $ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Refresh-Path'}, $true)
    Invoke-Expression $definition.Extent.Text
    $Destino = $testRoot
    Refresh-Path
    if ((Get-Command node.exe).Source -ne (Join-Path $local 'node.exe')) { throw 'Refresh-Path perdio el Node local.' }
    if ((& node.exe --version) -ne 'v24.22.3') { throw 'Version Node incorrecta.' }
    & npm.cmd --version
    if ($LASTEXITCODE -ne 0) { throw 'npm no funciona.' }
    & npx.cmd --version
    if ($LASTEXITCODE -ne 0) { throw 'npx no funciona.' }
    # Archivo corrupto: debe fallar antes de extraer y nunca anunciar exito.
    $badRoot = Join-Path $testRoot 'bad'
    $badInstallers = Join-Path $badRoot 'runtime\installers'
    New-Item -ItemType Directory -Path $badInstallers -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $badInstallers 'node-v24.22.3-win-x64.zip') -Value 'invalid'
    $env:Path = "$env:WINDIR\System32;$env:WINDIR"
    $rejected = $false
    try { Install-Node24 -Root $badRoot } catch {
        if ($_.Exception.Message -notlike '*SHA256 incorrecto*') { throw }
        $rejected = $true
    }
    if (!$rejected) { throw 'Se acepto un archivo corrupto.' }
    if ([Environment]::GetEnvironmentVariable('Path','User') -cne $userPath -or [Environment]::GetEnvironmentVariable('Path','Machine') -cne $machinePath) { throw 'La prueba altero PATH persistente.' }
    Write-Host 'OK: Node24/npm/npx reales, instalacion sin MSI, reutilizacion, Refresh-Path y rechazo SHA256.'
    Write-Host "Prueba aislada conservada en $testRoot"
} finally {
    $env:Path = $oldPath
}
