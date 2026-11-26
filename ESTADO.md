# Estado del proyecto
Fecha: 2026-11-25 (America/Buenos_Aires).
Hecho: gemini_ask(prompt) agregada al servidor real antigravity_mcp.mjs, conservando herramientas anteriores.
Respaldo: config_backups/antigravity_mcp_bak_20261125.mjs, identico al servidor previo.
Hecho: CLI real de Chat Fijo Gemini, stdin UTF-8, timeout externo 200 s, sin shell.
Hecho: recuperacion del verificador una vez y un reintento solo por conexion CDP 9222.
Hecho: regla agregada a ambas copias AGENTS.md preservando reglas anteriores y SHA256 identico.
Verificado: node --check y 10 pruebas; MCP stdio publica antigravity_ask, antigravity_status y gemini_ask.
Verificado: los tres scripts protegidos conservan SHA256; ninguna consulta enviada a modelos.
Limitacion: tool_timeout_sec=90 del cliente puede cortar antes; config.toml no fue modificado.
Proximo paso exacto: ajustar tool_timeout_sec=500 en [mcp_servers.antigravity_bridge] y recargar MCP o abrir una sesion nueva para habilitar gemini_ask.
