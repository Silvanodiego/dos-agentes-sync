@echo off
rem Panel y bandeja independientes, con mutex para evitar duplicados.
start "" /b "%~dp0.venv\Scripts\pythonw.exe" -X utf8 "%~dp0panel_control.py"
start "" /b "%~dp0.venv\Scripts\pythonw.exe" -X utf8 "%~dp0tray_monitor.py"
rem Iniciar el chat fijo solo si no existe un listener en 127.0.0.1:9222.
rem El chequeo TCP no envia mensajes ni interfiere con Cascada AG.
powershell.exe -NoProfile -Command "$tcp = New-Object System.Net.Sockets.TcpClient; $listening = $false; try { $pending = $tcp.ConnectAsync('127.0.0.1', 9222); if ($pending.Wait(1000)) { $listening = $tcp.Connected } } catch { } finally { $tcp.Dispose() }; if ($listening) { exit 0 } else { exit 1 }"
if errorlevel 1 call "%~dp0abrir_chrome_gemini_oculto.bat" >nul 2>&1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\sync_launcher.ps1" -Mode startup
exit /b %errorlevel%
