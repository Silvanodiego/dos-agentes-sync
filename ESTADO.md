# Estado del proyecto
Fecha: 2026-11-25 (America/Buenos_Aires).
Hecho: gemini_ask disponible en antigravity_mcp.mjs; respaldo y 10 pruebas aprobadas en el cambio anterior.
Hecho: tool_timeout_sec=500 en antigravity_bridge, tanto configuracion global como plantilla compartida.
Respaldo: config_backups/codex_config_bak_20261125_211756_404079.toml (local, no versionado por posible contenido sensible).
Verificado: ambas configuraciones TOML validas, solo cambio del timeout y UTF-8 sin BOM.
Verificado: no se modificaron AGENTS.md ni los scripts de los servicios.
Proximo paso exacto: recargar antigravity_bridge o abrir una sesion nueva para aplicar tool_timeout_sec=500.
