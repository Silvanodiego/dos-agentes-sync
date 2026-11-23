@echo off
setlocal
title Migracion Codex Limpia v5 - PC 3
echo Migracion Codex Limpia v5 - instalacion con progreso visible
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\instalar_pc3.ps1" %*
set "RESULTADO=%errorlevel%"
if not "%RESULTADO%"=="0" echo ERROR: instalacion incompleta. Revise el mensaje anterior.
if /I not "%~1"=="-Verificar" pause
exit /b %RESULTADO%
