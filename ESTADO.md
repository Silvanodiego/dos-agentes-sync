# Estado del proyecto
Fecha: 2026-11-26 (America/Buenos_Aires).
Hecho: respaldo previo exacto config_backups/chat_fijo_gemini_bak_20261126.py.
Hecho: --limpiar-borrador limpia y confirma editor vacio antes de enviar; sin flag conserva el borrador.
Hecho: gemini_ask pasa el flag automaticamente, manteniendo timeout y recuperacion CDP.
Verificado: py_compile, node --check, 4 pruebas Python mock y 10 pruebas MCP aprobadas.
Verificado: limpieza CLI con borrador envia una sola vez; fallo de limpieza no envia nada.
Pendiente ajeno: scripts/sdetecno/ con archivos preexistentes sin seguimiento; conservados intactos.
Proximo paso exacto: recargar el servidor MCP para que el proceso Node activo use el nuevo argumento.
