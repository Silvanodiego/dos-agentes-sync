# Instala o actualiza el verificador para el usuario actual (PC 1/2/3).
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [Console]::OutputEncoding
$ErrorActionPreference = 'Stop'
$root = 'C:\dos_agentes_local'
$verificador = Join-Path $root 'scripts\verificar_flujo_10m.ps1'
$log = Join-Path $root 'logs\verificador_10m.log'
if (-not (Test-Path -LiteralPath $verificador -PathType Leaf)) {
    throw "No existe el verificador: $verificador"
}
$taskCommand = 'powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\dos_agentes_local\scripts\verificar_flujo_10m.ps1"'
& schtasks.exe /Create /TN 'DosAgentes_Verificador_10m' /SC MINUTE /MO 10 /TR $taskCommand /F
if ($LASTEXITCODE -ne 0) { throw "No se pudo registrar la tarea: salida $LASTEXITCODE" }
& powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File $verificador
$checkExit = $LASTEXITCODE
if (Test-Path -LiteralPath $log) {
    Get-Content -LiteralPath $log -Encoding UTF8 -Tail 1
} else {
    throw 'El verificador no genero su log.'
}
if ($checkExit -ne 0) {
    Write-Warning "Tarea registrada; la verificacion inmediata fallo (salida $checkExit)."
}
exit $checkExit
