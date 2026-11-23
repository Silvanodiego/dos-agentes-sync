@echo off
setlocal
if /I "%~1"=="--version" goto version
if /I "%~1"=="-v" goto version
if not defined DOS_AGENTES_ROOT set "DOS_AGENTES_ROOT=C:\dos_agentes_local"
"%DOS_AGENTES_ROOT%\.venv\Scripts\python.exe" -X utf8 "%DOS_AGENTES_ROOT%\agy_passthrough.py" %*
exit /b %errorlevel%
:version
echo agy 1.0.0
exit /b 0
