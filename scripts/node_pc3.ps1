# Node oficial con npm y npx completos; alternativa al MSI que falla con 1603.
Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop
Import-Module Microsoft.PowerShell.Archive -ErrorAction Stop
function Enable-NodePath {
    param([string]$Directory, [switch]$Persist)
    $env:Path = $Directory + ';' + (($env:Path -split ';' | Where-Object { $_ -and $_.TrimEnd('\') -ine $Directory.TrimEnd('\') }) -join ';')
    if ($Persist) {
        $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
        $entries = @($userPath -split ';' | Where-Object { $_ -and $_.TrimEnd('\') -ine $Directory.TrimEnd('\') })
        [Environment]::SetEnvironmentVariable('Path', ($Directory + ';' + ($entries -join ';')), 'User')
        # Windows antepone PATH Machine al User: un Node anterior no debe ganar.
        $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        if ($admin) {
            $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
            $entries = @($machinePath -split ';' | Where-Object { $_ -and $_.TrimEnd('\') -ine $Directory.TrimEnd('\') })
            [Environment]::SetEnvironmentVariable('Path', ($Directory + ';' + ($entries -join ';')), 'Machine')
        }
    }
}

function Test-Node24 {
    param([string]$Directory)
    foreach ($file in @('node.exe','npm.cmd','npx.cmd')) {
        if (!(Test-Path -LiteralPath (Join-Path $Directory $file) -PathType Leaf)) { return $false }
    }
    $version = & (Join-Path $Directory 'node.exe') --version
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^v24\.') { return $false }
    # npm.cmd/npx.cmd deben usar el node.exe de su misma carpeta.
    foreach ($file in @('npm.cmd','npx.cmd')) {
        $version = & (Join-Path $Directory $file) --version
        if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.') { return $false }
    }
    return $true
}

function Install-Node24 {
    param([Parameter(Mandatory=$true)][string]$Root, [switch]$Persist)
    $local = Join-Path $Root 'runtime\node-v24.22.3-win-x64'
    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    foreach ($candidate in @($local, $(if ($node) { Split-Path $node.Source -Parent }))) {
        if ($candidate -and (Test-Node24 -Directory $candidate)) {
            Enable-NodePath -Directory $candidate -Persist:$Persist
            Write-Host "Node.js 24, npm y npx verificados: $candidate"
            return
        }
    }
    if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { throw 'Este paquete Node reproduce PC1 x64; no admite ARM64.' }
    $archive = Join-Path $Root 'runtime\installers\node-v24.22.3-win-x64.zip'
    $expected = 'e612af99f626ab415ea225af6bce5c971feb448cb5cae250bb1c3fa50c5f7d9f'
    if (!(Test-Path -LiteralPath $archive)) { throw 'Falta la distribucion oficial completa de Node.js incluida en el paquete.' }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ine $expected) { throw 'SHA256 incorrecto de Node.js; no se instala.' }
    if (Test-Path -LiteralPath $local) {
        $runtimeRoot = [IO.Path]::GetFullPath((Join-Path $Root 'runtime')).TrimEnd('\') + '\'
        $backup = $local + '.incompleto-' + [guid]::NewGuid()
        foreach ($path in @($local, $backup)) {
            if (!([IO.Path]::GetFullPath($path).StartsWith($runtimeRoot, [StringComparison]::OrdinalIgnoreCase))) { throw 'Ruta Node fuera del runtime autorizado.' }
        }
        Move-Item -LiteralPath $local -Destination $backup
        Write-Host "Runtime incompleto conservado en $backup; instalando copia completa."
    }
    Write-Host 'Instalando Node.js 24.22.3 completo (node, npm y npx), sin depender del MSI...'
    Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $Root 'runtime')
    if (!(Test-Node24 -Directory $local)) { throw 'Node.js/npm/npx no superaron la verificacion; instalacion incompleta.' }
    Enable-NodePath -Directory $local -Persist:$Persist
    Write-Host "Node.js 24, npm y npx instalados y verificados: $local"
}
