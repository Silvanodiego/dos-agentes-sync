@echo off
rem Iniciar el chat fijo solo si no existe un listener en 127.0.0.1:9222.
rem El chequeo TCP no envia mensajes ni interfiere con Cascada AG.
powershell.exe -NoProfile -Command "$tcp = New-Object System.Net.Sockets.TcpClient; $listening = $false; try { $pending = $tcp.ConnectAsync('127.0.0.1', 9222); if ($pending.Wait(1000)) { $listening = $tcp.Connected } } catch { } finally { $tcp.Dispose() }; if ($listening) { exit 0 } else { exit 1 }"
if errorlevel 1 call "%~dp0abrir_chrome_gemini.bat"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\sync_launcher.ps1" -Mode startup
exit /b %errorlevel%
