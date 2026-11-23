# Codex con puente y Antigravity

Usa automaticamente el MCP antigravity_bridge para delegar analisis, investigacion,
revision y subtareas adecuadas segun el pedido del usuario. La herramienta
antigravity_ask conecta al puente local http://127.0.0.1:8765, que consulta
Antigravity Manager en http://127.0.0.1:8045. Usa Gemini Argon
(gemini-4-argon-high) por defecto mientras tenga cuota; respeta el modelo pedido.

Codex conserva el contexto principal, aplica cambios y verifica localmente los
resultados delegados. Envia solo el contexto necesario, sin credenciales. Las
operaciones simples pueden ejecutarse directamente. Si el MCP no esta disponible,
informa el fallo y consulta el adaptador agy mediante su skill; no ocultes errores
ni reintentes inferencias fallidas sin pedido del usuario. No se exige auto.bat.
El monitor administra la cuenta activa de Codex Desktop y sus cambios por cuota.
No incluyas cabeceras de coordinacion o delegacion en las respuestas.

## Sincronizacion obligatoria

Cada vez que modifiques cualquier archivo en C:\dos_agentes_local\ o en config_compartida\, al terminar la tarea ejecutá automáticamente git add, git commit con un mensaje breve y git push.

Ejecuta estos comandos con C:\dos_agentes_local como directorio de trabajo.
Respeta .gitignore, nunca uses git add -f para credenciales o sesiones.
Si no hay remoto o falla la red, conserva el commit local e informa el pendiente.
Edita las reglas compartidas en config_compartida\AGENTS.md; el sincronizador las
copia a %USERPROFILE%\.codex\AGENTS.md y al AGENTS.md de este repositorio.
