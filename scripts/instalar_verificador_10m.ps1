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
# Sincroniza reglas globales antes de registrar la tarea.
$utf8NoBom = New-Object System.Text.UTF8Encoding($false, $true)
$codexDir = Join-Path $env:USERPROFILE '.codex'
$agentsSource = Join-Path $root 'AGENTS.md'
$agentsTarget = Join-Path $codexDir 'AGENTS.md'
$backupDir = Join-Path $root 'config_backups'
New-Item -ItemType Directory -Path $codexDir -Force | Out-Null
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$agentsText = [System.IO.File]::ReadAllText($agentsSource, $utf8NoBom)
[System.IO.File]::WriteAllText($agentsTarget, $agentsText, $utf8NoBom)
if ((Get-FileHash -LiteralPath $agentsSource -Algorithm SHA256).Hash -ne
    (Get-FileHash -LiteralPath $agentsTarget -Algorithm SHA256).Hash) {
    throw 'Las reglas globales no coinciden byte a byte con AGENTS.md del repositorio.'
}

function Update-CodexMcpTimeout {
    param([string]$ConfigPath, [string]$BackupDirectory)
    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        throw "Falta configurar antigravity_bridge en: $ConfigPath"
    }
    $encoding = New-Object System.Text.UTF8Encoding($false, $true)
    $text = [System.IO.File]::ReadAllText($ConfigPath, $encoding)
    # Limita el reemplazo a la tabla exacta y termina en la siguiente tabla TOML.
    $sectionRegex = [regex]'(?m)^[ \t]*\[mcp_servers\.antigravity_bridge\][ \t]*(?:#[^\r\n]*)?\r?\n(?:(?!^[ \t]*\[)[\s\S])*'
    $sections = $sectionRegex.Matches($text)
    if ($sections.Count -ne 1) {
        throw 'Se requiere una unica seccion [mcp_servers.antigravity_bridge] existente.'
    }
    $section = $sections[0]
    $timeoutRegex = [regex]'(?m)^([ \t]*tool_timeout_sec[ \t]*=[ \t]*)[0-9]+([ \t]*(?:#[^\r\n]*)?)(\r?)$'
    $timeouts = $timeoutRegex.Matches($section.Value)
    if ($timeouts.Count -gt 1) { throw 'tool_timeout_sec esta duplicado en antigravity_bridge.' }
    if ($timeouts.Count -eq 1) {
        $updatedSection = $timeoutRegex.Replace($section.Value, '${1}500${2}${3}', 1)
    } else {
        if ($section.Value -match '(?m)^[ \t]*tool_timeout_sec[ \t]*=') {
            throw 'tool_timeout_sec tiene un formato inesperado; no se modifica.'
        }
        $updatedSection = $section.Value.TrimEnd([char[]]"`r`n") + "`r`ntool_timeout_sec = 500`r`n`r`n"
    }
    $updated = $text.Substring(0, $section.Index) + $updatedSection + $text.Substring($section.Index + $section.Length)
    if ($updated -cne $text) {
        $backupName = 'codex_config_timeout_bak_' + [DateTime]::Now.ToString('yyyyMMdd_HHmmss_fffffff') + '.toml'
        Copy-Item -LiteralPath $ConfigPath -Destination (Join-Path $BackupDirectory $backupName) -ErrorAction Stop
        [System.IO.File]::WriteAllText($ConfigPath, $updated, $encoding)
        Write-Output 'Timeout de antigravity_bridge actualizado a 500; respaldo local conservado.'
    } else {
        Write-Output 'Timeout de antigravity_bridge ya configurado en 500.'
    }
}
Update-CodexMcpTimeout -ConfigPath (Join-Path $codexDir 'config.toml') -BackupDirectory $backupDir

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
