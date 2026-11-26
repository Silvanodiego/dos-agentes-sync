# Estado del proyecto
Fecha: 2026-11-25 (America/Buenos_Aires).
Hecho: respaldo previo global en config_backups/codex_agents_bak_20261125.md (local).
Hecho: AGENTS.md global copiado del repositorio, SHA256 identico y UTF-8 sin BOM.
Hecho: instalador verificador copia reglas siempre y aplica timeout MCP 500 con respaldo si cambia config.toml.
Hecho: mantiene tarea DosAgentes_Verificador_10m cada 10 minutos y comprobacion inmediata.
Verificado: parser PowerShell y pruebas aisladas de actualizacion, respaldo, idempotencia y timeout ausente.
Verificado: TOML global valido y timeout 500; instalador real salida 0, 2026-11-25 21:23:25 -03:00 OK.
Pendiente: recargar MCP o abrir nueva sesion para aplicar configuracion al cliente.
Proximo paso exacto en PC 2/3: actualizar main y ejecutar powershell -NoProfile -ExecutionPolicy Bypass -File C:\dos_agentes_local\scripts\instalar_verificador_10m.ps1.
