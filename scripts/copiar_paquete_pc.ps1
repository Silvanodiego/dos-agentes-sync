# Conserva siempre los tres scripts protegidos que ya existen en destino.
function Copy-PackageFiles {
    param([string]$SourceRoot, [string]$DestinationRoot, $Manifest)
    if ([IO.Path]::GetFullPath($SourceRoot).TrimEnd('\') -eq [IO.Path]::GetFullPath($DestinationRoot).TrimEnd('\')) { return }
    $audit = @()
    foreach ($entry in $Manifest.files) {
        $target = Join-Path $DestinationRoot $entry.path
        if ((Test-Path -LiteralPath $target -PathType Leaf) -and
            $entry.path -match '(^|[\\/])(bridge_server|consultar_gemini|bucle_autonomo)\.py$') {
            $localHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
            $different = $localHash -ne $entry.sha256
            $audit += [pscustomobject]@{
                path = $entry.path; local_sha256 = $localHash; package_sha256 = $entry.sha256
                status = $(if ($different) { 'PRESERVED_DIVERGENT' } else { 'PRESERVED_IDENTICAL' })
            }
            if ($different) { Write-Warning "Se conserva sin modificar $($entry.path): difiere del paquete. La instalacion continua; ver logs\instalacion_archivos_protegidos.json." }
            continue
        }
        New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent) | Out-Null
        Copy-Item -LiteralPath (Join-Path $SourceRoot $entry.path) -Destination $target -Force
    }
    $logDirectory = Join-Path $DestinationRoot 'logs'
    New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
    ConvertTo-Json -InputObject @($audit) -Depth 4 |
        Set-Content -LiteralPath (Join-Path $logDirectory 'instalacion_archivos_protegidos.json') -Encoding UTF8
    $script:PreservedDifferences = @($audit | Where-Object status -eq 'PRESERVED_DIVERGENT')
}
