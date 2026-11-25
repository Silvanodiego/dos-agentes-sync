@echo off
setlocal
cd /d C:\dos_agentes_local
set "PSModulePath=%SystemRoot%\System32\WindowsPowerShell\v1.0\Modules;%ProgramFiles%\WindowsPowerShell\Modules"
echo Verificando activacion y primera sincronizacion sin cerrar Codex...
set "GIT_TERMINAL_PROMPT=0"
set "GCM_INTERACTIVE=never"
git pull --ff-only
if errorlevel 1 echo AVISO: no se pudo actualizar el repositorio. Se revisara la copia local.
if not exist ".venv\Scripts\python.exe" goto falta
if not exist "scripts\chats\activar_cuando_listo.py" goto falta
".venv\Scripts\python.exe" "scripts\chats\activar_cuando_listo.py" --root "C:\dos_agentes_local"
if not exist "scripts\chats\diagnosticar_sync.ps1" goto informe_local
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\chats\diagnosticar_sync.ps1" > "%TEMP%\diagnostico_chats_v8.txt" 2>&1
goto mostrar
:informe_local
powershell.exe -NoProfile -Command "Get-Content -LiteralPath (Join-Path $env:LOCALAPPDATA 'CodexSync\activation-status.json'),(Join-Path $env:LOCALAPPDATA 'CodexSync\live-sync-status.json') -ErrorAction Continue; Get-ScheduledTask -TaskName 'CodexChats*' -ErrorAction SilentlyContinue | Get-ScheduledTaskInfo | Format-List" > "%TEMP%\diagnostico_chats_v8.txt" 2>&1
:mostrar
type "%TEMP%\diagnostico_chats_v8.txt"
echo.
echo Informe guardado en %TEMP%\diagnostico_chats_v8.txt
pause
exit /b
:falta
echo ERROR: falta la instalacion V8 en C:\dos_agentes_local.
pause
exit /b 1
