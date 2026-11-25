# Estado del proyecto
Fecha: 2026-11-25 (America/Buenos_Aires).
Hecho: creado scripts/verificar_flujo_10m.ps1; verificacion pasiva local sin prompts.
Hecho: tarea DosAgentes_Verificador_10m habilitada para HP\H_P cada 10 minutos, PowerShell oculto.
Verificado: sintaxis PowerShell; timeout 4 s por chequeo; log UTF-8 sin BOM, maximo 200 lineas.
Prueba real: TCP 8765 y 8045 responden. CDP 9222 responde, pero no tiene pestaña Gemini; salida 1.
Protegidos: bridge_server.py, piloto_gemini.py, chat_fijo_gemini.py y AGENTS.md intactos.
Proximo paso exacto: abrir abrir_chrome_gemini.bat para disponer de una pestaña Gemini y repetir el verificador.
Alternativa: abrir https://gemini.google.com/app en el navegador ya conectado a CDP 9222.
