"""Build one double-click BAT with an allowlisted, self-contained repair payload."""
import argparse
import base64
import hashlib
import io
from pathlib import Path
import zipfile

FILES = (
    'sync_chats_abierto.py', 'backup_chats.py', 'coverage_chats.py',
    'proyectos_portables.py', 'continuidad_chats.py', 'rutas_historial.py',
    'activar_sync_abierto.ps1', 'activar_cuando_listo.py',
    'registrar_activacion_automatica.ps1', 'diagnosticar_sync.ps1', 'reparar_aislado.ps1',
)

HEADER = r'''@echo off
setlocal
set "CODEX_REPAIR_SELF=%~f0"
set "PSModulePath=%SystemRoot%\System32\WindowsPowerShell\v1.0\Modules;%ProgramFiles%\WindowsPowerShell\Modules"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$lines=[IO.File]::ReadAllLines($env:CODEX_REPAIR_SELF);$marker=[Array]::IndexOf($lines,'# POWERSHELL_START'); & ([scriptblock]::Create(($lines[($marker+1)..($lines.Length-1)] -join [Environment]::NewLine)))"
set "REPAIR_RESULT=%ERRORLEVEL%"
if not "%REPAIR_RESULT%"=="0" echo REPARACION PENDIENTE. Lea el error y el informe. No se anuncia exito.
pause
exit /b %REPAIR_RESULT%
# POWERSHELL_START
'''

BODY = r'''
$ErrorActionPreference = 'Stop'
$local = Join-Path $env:LOCALAPPDATA 'CodexSync'
New-Item -ItemType Directory -Path $local -Force | Out-Null
$log = Join-Path $local 'reparacion-chats-v8.txt'
Start-Transcript -LiteralPath $log -Append | Out-Null
try {
    Write-Host 'Reparacion V8 adaptable: JSONL + indice o historial SQLite; sin cerrar Codex.'
    $bytes = [Convert]::FromBase64String($payload)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $actual = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose() }
    if ($actual -ne $expected) { throw 'El paquete de reparacion esta alterado o incompleto.' }
    $runner = Join-Path $local ('runner-' + $expected.Substring(0,16))
    New-Item -ItemType Directory -Path $runner -Force | Out-Null
    $prefix = [IO.Path]::GetFullPath($runner).TrimEnd('\') + '\'
    Add-Type -AssemblyName System.IO.Compression
    $stream = [IO.MemoryStream]::new($bytes, $false)
    $zip = [IO.Compression.ZipArchive]::new($stream, [IO.Compression.ZipArchiveMode]::Read)
    try {
        foreach ($entry in $zip.Entries) {
            $destination = [IO.Path]::GetFullPath((Join-Path $runner $entry.FullName))
            if (!$destination.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Ruta de paquete rechazada.' }
            $parent = Split-Path -Parent $destination
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
            if ((Get-Item -LiteralPath $parent -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Directorio enlazado rechazado.' }
            $inputStream = $entry.Open()
            try {
                $memory = [IO.MemoryStream]::new()
                try { $inputStream.CopyTo($memory); $content = $memory.ToArray() }
                finally { $memory.Dispose() }
            } finally { $inputStream.Dispose() }
            if (Test-Path -LiteralPath $destination) {
                if ((Get-Item -LiteralPath $destination -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Archivo enlazado rechazado.' }
                $existing = [IO.File]::ReadAllBytes($destination)
                if ([Convert]::ToBase64String($existing) -ne [Convert]::ToBase64String($content)) {
                    throw ('Se conserva el modulo local modificado: ' + $destination)
                }
            } else { [IO.File]::WriteAllBytes($destination, $content) }
        }
    } finally { $zip.Dispose(); $stream.Dispose() }
    & (Join-Path $runner 'scripts\chats\reparar_aislado.ps1')
} catch {
    Write-Host ('ERROR: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Informe: ' + $log)
    Stop-Transcript | Out-Null
    exit 1
}
Write-Host ('Informe: ' + $log)
Stop-Transcript | Out-Null
exit 0
'''


def build(root, output):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            entry = zipfile.ZipInfo('scripts/chats/' + name, date_time=(2026, 11, 24, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, (root / 'scripts/chats' / name).read_bytes())
    payload = buffer.getvalue()
    text = HEADER + "$expected = '" + hashlib.sha256(payload).hexdigest() + "'\n$payload = '" + base64.b64encode(payload).decode('ascii') + "'\n" + BODY
    output.write_bytes(text.replace('\r\n', '\n').replace('\n', '\r\n').encode('ascii'))
    return len(payload)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(build(Path(__file__).resolve().parent.parent, args.output))
