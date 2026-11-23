@echo off
setlocal
rem No abrir otra instancia si CDP ya esta escuchando.
powershell.exe -NoProfile -Command "$tcp = New-Object System.Net.Sockets.TcpClient; $listening = $false; try { $pending = $tcp.ConnectAsync('127.0.0.1', 9222); if ($pending.Wait(1000)) { $listening = $tcp.Connected } } catch { } finally { $tcp.Dispose() }; if ($listening) { exit 0 } else { exit 1 }"
if not errorlevel 1 exit /b 0
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
rem Headless no crea ventana ni boton en la barra de tareas.
start "" /b "%GEMINI_BROWSER%" --headless=new --remote-debugging-port=9222 --user-data-dir="C:\dos_agentes_local\chrome_gemini_profile" --no-first-run --no-default-browser-check "https://gemini.google.com/app" >nul 2>&1
if errorlevel 1 exit /b 3
rem Espera acotada para que el sincronizador no lance una segunda instancia.
powershell.exe -NoProfile -Command "$limit = [DateTime]::UtcNow.AddSeconds(15); do { $tcp = New-Object System.Net.Sockets.TcpClient; try { $pending = $tcp.ConnectAsync('127.0.0.1', 9222); if ($pending.Wait(500) -and $tcp.Connected) { exit 0 } } catch { } finally { $tcp.Dispose() }; Start-Sleep -Milliseconds 250 } while ([DateTime]::UtcNow -lt $limit); exit 3"
exit /b %errorlevel%
