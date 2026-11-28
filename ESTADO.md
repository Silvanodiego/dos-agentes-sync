# Estado del proyecto
Fecha: 2026-11-27 (America/Buenos_Aires).
Hecho: respaldos previos MCP y Chat Fijo en config_backups con fecha 20261127.
Hecho: IDs AG/GEM-HHMMSS-XXXX al final de las respuestas MCP y auditoria local sin prompts ni credenciales.
Hecho: auditoria limitada a 500 lineas; escrituras coordinadas con espera maxima de 2 segundos.
Hecho: conservado --limpiar-borrador existente y su uso desde gemini_ask.
Hecho: bloque inicial anti-bloqueo actualizado; ambas reglas del repo copiadas al AGENTS global.
Hecho: clave publica SSH local y Host nas verificados, sin versionar llaves/config SSH.
Verificado: node --check antigravity_mcp.mjs y python -m py_compile chat_fijo_gemini.py.
Verificado: 16 pruebas Node y 4 Python aprobadas con mocks; sin llamadas a modelos.
Verificado: bridge_server.py y piloto_gemini.py conservados; scripts/sdetecno/ fuera de este cambio.
Bloqueos: ninguno en las comprobaciones locales.
Proximo paso exacto: recargar el servidor MCP en la proxima sesion para utilizar el codigo actualizado.

## NAS
- SSH por clave verificado con la cuenta normal.
- Agrupados y verificados seis episodios de Avatar en la carpeta indexada, con originales intactos.
- Pendiente: iniciar escaneo de Peliculas y series desde Jellyfin y verificar seis entradas en el indice.
