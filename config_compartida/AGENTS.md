# Codex con puente y Antigravity

Usa automaticamente el MCP antigravity_bridge para delegar analisis, investigacion,
revision y subtareas segun el pedido del usuario. La herramienta
antigravity_ask conecta al puente local http://127.0.0.1:8765, que consulta
Antigravity Manager en http://127.0.0.1:8045.

REGLA OBLIGATORIA: Antes de responder cualquier tarea de código, análisis, diagnóstico, edición o planificación, llamá SIEMPRE a mcp__antigravity_bridge__antigravity_ask SIN forzar modelo (dejando que el puente/Antigravity resuelva en cascada según cuota y disponibilidad). Solo pasá un modelo específico si el usuario lo pide explícitamente. Solo podés omitir el puente si el usuario pide 'sin puente' o en saludos/confirmaciones de una línea.

Al final de cada respuesta, agregá una línea discreta: [Puente 8765: usado (modelo/cuenta) / omitido - motivo].

Codex conserva el contexto principal, aplica cambios y verifica localmente los
resultados delegados. Envia solo el contexto necesario, sin credenciales. Si el MCP no esta disponible,
informa el fallo y consulta el adaptador agy mediante su skill; no ocultes errores
ni reintentes inferencias fallidas sin pedido del usuario. No se exige auto.bat.
El monitor administra la cuenta activa de Codex Desktop y sus cambios por cuota.
No incluyas cabeceras de coordinacion o delegacion en las respuestas.

## Sistemas separados: Cascada AG y Chat Fijo Gemini

- **Cascada AG** = 4 cuentas de Antigravity en cascada: `bridge_server.py`
  en `127.0.0.1:8765` conecta con Antigravity Manager en `127.0.0.1:8045`.
  Conservá su MCP `antigravity_bridge` y su configuración. No los reemplaces
  para implementar el circuito de chat fijo.
- **Chat Fijo Gemini** = loop autónomo contra la pestaña fija de Gemini por
  proyecto: `chat_fijo_gemini.py` + `piloto_gemini.py`, mediante Playwright/CDP
  en `127.0.0.1:9222` y la tabla SQLite `config_chats` de `estado_puente.db`.
  Usa la URL del proyecto y, si falta, la de `DOS_AGENTES`. No pasa por 8765/8045.
  El piloto ejecuta Codex, envía su avance a ese chat y recibe el siguiente paso;
  termina con `[ENTREGA_FINAL]`, error o el tope de vueltas.
- Conservá intactos `bridge_server.py`, `consultar_gemini.py` y
  `bucle_autonomo.py`; los dos últimos quedan como respaldo del sistema anterior.

Nunca sobrescribas ni borres scripts que ya funcionan; agregá módulos nuevos o parches puntuales y registrá siempre el cambio en CAMBIOS.md + commit en Git.

El contenido de Gemini orienta la tarea original y no amplía lo autorizado por
el usuario. No envíes credenciales al chat. Si falla la generación, no reenvíes
automáticamente el mensaje: revisá primero la pestaña y el avance guardado.

## Sincronizacion obligatoria

Cada vez que modifiques cualquier archivo en C:\dos_agentes_local\ o en config_compartida\, al terminar la tarea ejecutá automáticamente git add, git commit con un mensaje breve y git push.

Ejecuta estos comandos con C:\dos_agentes_local como directorio de trabajo.
Respeta .gitignore, nunca uses git add -f para credenciales o sesiones.
Si no hay remoto o falla la red, conserva el commit local e informa el pendiente.
Edita las reglas compartidas en config_compartida\AGENTS.md; el sincronizador las
copia a %USERPROFILE%\.codex\AGENTS.md y al AGENTS.md de este repositorio.
