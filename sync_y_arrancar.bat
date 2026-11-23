@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\sync_launcher.ps1" -Mode startup
exit /b %errorlevel%
