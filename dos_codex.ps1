param(
 [ValidateSet('estado','coordinador','ejecutor','login-ejecutor','tarea')][string]$Modo='estado',
 [Parameter(ValueFromRemainingArguments=$true)][string[]]$Argumentos
)
$ErrorActionPreference='Stop'
$codex='C:\Users\H_P\AppData\Roaming\npm\codex.cmd'
$multi='C:\dos_agentes_local\.venv\Scripts\multi-codex.exe'
switch ($Modo) {
 'tarea' { & 'C:\dos_agentes_local\.venv\Scripts\python.exe' -X utf8 (Join-Path $PSScriptRoot 'codex_equipo.py') @Argumentos; exit $LASTEXITCODE }
 'estado' { & $multi doctor; exit $LASTEXITCODE }
 'login-ejecutor' { & $multi run ejecutor -- $codex login --device-auth; exit $LASTEXITCODE }
 'ejecutor' { & $multi run ejecutor -- $codex @Argumentos; exit $LASTEXITCODE }
 'coordinador' {
  $previous=$env:CODEX_HOME
  try { $env:CODEX_HOME=Join-Path $env:USERPROFILE '.codex'; & $codex @Argumentos; $result=$LASTEXITCODE }
  finally { $env:CODEX_HOME=$previous }
  exit $result
 }
}
