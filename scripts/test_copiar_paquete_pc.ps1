$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'copiar_paquete_pc.ps1')
$testRoot = Join-Path $env:TEMP ('instalador preservacion ' + [guid]::NewGuid())
$src = Join-Path $testRoot 'paquete'
$dst = Join-Path $testRoot 'destino'
New-Item -ItemType Directory -Force -Path $src,$dst | Out-Null
$names = @('bridge_server.py','consultar_gemini.py','bucle_autonomo.py','normal.py')
foreach ($name in $names) { Set-Content -LiteralPath (Join-Path $src $name) -Value '# paquete' }
$manifest = @{ files = @($names | ForEach-Object { @{path=$_; sha256=(Get-FileHash -LiteralPath (Join-Path $src $_)).Hash} }) }
Copy-PackageFiles $src $dst $manifest
foreach ($name in $names) {
    if ((Get-FileHash (Join-Path $src $name)).Hash -ne (Get-FileHash (Join-Path $dst $name)).Hash) { throw 'Instalacion limpia incompleta.' }
}
Copy-PackageFiles $src $dst $manifest
if ($script:PreservedDifferences.Count) { throw 'Falsa divergencia en reinstalacion.' }
$before = @{}
foreach ($name in $names[0..2]) {
    $file = Join-Path $dst $name
    Set-Content -LiteralPath $file -Value '# version local diferente'
    (Get-Item $file).LastWriteTimeUtc = [datetime]'2020-01-01'
    $before[$name] = @((Get-FileHash $file).Hash,(Get-Item $file).LastWriteTimeUtc)
}
foreach ($round in 1..2) {
    Set-Content (Join-Path $dst 'normal.py') -Value '# copia incompleta'
    Copy-PackageFiles $src $dst $manifest
    foreach ($name in $names[0..2]) {
        $file = Join-Path $dst $name
        if ((Get-FileHash $file).Hash -ne $before[$name][0] -or (Get-Item $file).LastWriteTimeUtc -ne $before[$name][1]) { throw "Se modifico un protegido: $name" }
    }
    if ((Get-FileHash (Join-Path $src 'normal.py')).Hash -ne (Get-FileHash (Join-Path $dst 'normal.py')).Hash) { throw 'No se actualizo archivo normal.' }
    $audit = Get-Content (Join-Path $dst 'logs\instalacion_archivos_protegidos.json') -Raw | ConvertFrom-Json
    if ($audit.Count -ne 3 -or @($audit | Where-Object status -ne 'PRESERVED_DIVERGENT').Count) { throw 'Auditoria incompleta.' }
}
Write-Host 'OK: instalacion limpia, identica, divergente y reanudacion; hashes y fechas protegidas intactas.'
# Se conserva el fixture temporal para inspeccion; no toca el repositorio ni servicios.
