@echo off
setlocal
title Migracion Codex Limpia v8 - PC 2 / PC 3
echo Migracion Codex Limpia v8 - instalacion con progreso visible
rem Evita heredar modulos PowerShell 7 incompatibles al abrir Windows PowerShell 5.1.
set "PSModulePath=%SystemRoot%\System32\WindowsPowerShell\v1.0\Modules;%ProgramFiles%\WindowsPowerShell\Modules"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\instalar_pc3.ps1" %*
set "RESULTADO=%errorlevel%"
if not "%RESULTADO%"=="0" echo ERROR: instalacion incompleta. Revise el mensaje anterior.
if /I not "%~1"=="-Verificar" pause
exit /b %RESULTADO%
