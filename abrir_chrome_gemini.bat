@echo off
setlocal
set "GEMINI_BROWSER="
for %%B in (
  "%ProgramFiles%\Google\Chrome\Application\chrome.exe"
  "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
  "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
) do if not defined GEMINI_BROWSER if exist "%%~B" set "GEMINI_BROWSER=%%~B"
if not defined GEMINI_BROWSER for /f "delims=" %%B in ('where chrome.exe 2^>nul') do if not defined GEMINI_BROWSER set "GEMINI_BROWSER=%%B"
if not defined GEMINI_BROWSER for %%B in (
  "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
  "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
  "%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"
) do if not defined GEMINI_BROWSER if exist "%%~B" set "GEMINI_BROWSER=%%~B"
if not defined GEMINI_BROWSER for /f "delims=" %%B in ('where msedge.exe 2^>nul') do if not defined GEMINI_BROWSER set "GEMINI_BROWSER=%%B"
if not defined GEMINI_BROWSER (
  echo ERROR: No se encontro Google Chrome ni Microsoft Edge. 1>&2
  exit /b 2
)
start "" "%GEMINI_BROWSER%" --remote-debugging-port=9222 --user-data-dir="C:\dos_agentes_local\chrome_gemini_profile" "https://gemini.google.com/app"
if errorlevel 1 exit /b 3
exit /b 0
