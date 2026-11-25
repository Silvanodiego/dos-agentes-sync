[CmdletBinding()]
param([switch]$Ejecutar)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
$temporaryPath = 'C:\dos_agentes_local\codex_temporal'
$rulesPath = 'C:\dos_agentes_local\.agents\rules\workspace-rules.md'

try {
    if (-not $Ejecutar) {
        Write-Output ('SIMULACI' + [char]0x00D3 + 'N: no se borra nada.')
        Write-Output ('Se borraria de forma recursiva: ' + $temporaryPath + '\')
        if (Test-Path -LiteralPath $temporaryPath -PathType Container) {
            Write-Output 'Contenido actual:'
            Get-ChildItem -LiteralPath $temporaryPath -Recurse -Force |
                Sort-Object FullName | ForEach-Object { Write-Output $_.FullName }
        } else {
            Write-Output 'La carpeta temporal no existe.'
        }
        exit 0
    }

    if (-not (Test-Path -LiteralPath $rulesPath -PathType Leaf)) {
        throw ('No se puede comprobar la integridad: falta ' + $rulesPath)
    }
    $rulesBefore = Get-Item -LiteralPath $rulesPath
    $rulesHashBefore = (Get-FileHash -LiteralPath $rulesPath -Algorithm SHA256).Hash
    $rulesTimeBefore = $rulesBefore.LastWriteTimeUtc

    if (Test-Path -LiteralPath $temporaryPath) {
        $target = Get-Item -LiteralPath $temporaryPath -Force
        $resolvedPath = (Resolve-Path -LiteralPath $temporaryPath).ProviderPath
        if (-not $target.PSIsContainer -or $resolvedPath.TrimEnd('\') -ine $temporaryPath) {
            throw 'El destino resuelto no coincide con la carpeta temporal autorizada.'
        }
        if ($target.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            throw 'La carpeta temporal es un enlace; no se elimina.'
        }
        $linkedEntries = @(Get-ChildItem -LiteralPath $temporaryPath -Recurse -Force |
            Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint })
        if ($linkedEntries.Count -gt 0) {
            throw 'Hay enlaces dentro de la carpeta temporal; revisar manualmente antes de eliminar.'
        }
        Remove-Item -LiteralPath $resolvedPath -Recurse -Force
    }
    if (Test-Path -LiteralPath $temporaryPath) { throw 'La carpeta temporal sigue existiendo.' }
    if (-not (Test-Path -LiteralPath $rulesPath -PathType Leaf)) { throw 'Falta el archivo de reglas permanentes.' }
    $rulesHashAfter = (Get-FileHash -LiteralPath $rulesPath -Algorithm SHA256).Hash
    $rulesTimeAfter = (Get-Item -LiteralPath $rulesPath).LastWriteTimeUtc
    if ($rulesHashAfter -cne $rulesHashBefore -or $rulesTimeAfter -ne $rulesTimeBefore) {
        throw 'El archivo de reglas permanentes cambio durante el desmontaje.'
    }
    Write-Output ('Reglas permanentes intactas: ' + $rulesPath)
    Write-Output 'Desmontaje terminado.'
    Write-Output 'desactivar_codex.ps1 puede borrarse manualmente o con git rm si esta versionado.'
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
