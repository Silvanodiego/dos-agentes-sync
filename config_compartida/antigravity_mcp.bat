@echo off
setlocal
if not defined DOS_AGENTES_ROOT set "DOS_AGENTES_ROOT=C:\dos_agentes_local"
node.exe "%DOS_AGENTES_ROOT%\antigravity_mcp.mjs"
exit /b %errorlevel%
