@echo off
wscript.exe //B //Nologo "%~dp0scripts\sync_silencioso.vbs" periodic
exit /b %errorlevel%
