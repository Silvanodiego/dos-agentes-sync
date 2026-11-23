@echo off
setlocal
set "DOS_AGENTES_ROOT=C:\dos_agentes_local"
"%DOS_AGENTES_ROOT%\.venv\Scripts\python.exe" -X utf8 "%DOS_AGENTES_ROOT%\agy_passthrough.py" %*
exit /b %errorlevel%
