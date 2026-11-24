@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\chats\activar_sync_abierto.ps1"
if errorlevel 1 (
  echo No se completo la activacion. Revise el error anterior.
  pause
  exit /b 1
)
echo Sincronizador instalado para esta PC. Codex puede continuar abierto.
pause
