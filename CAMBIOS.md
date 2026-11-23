# Registro de cambios

## 2026-11-23 — Chat Fijo Gemini independiente de Cascada AG

Archivos nuevos en `C:\dos_agentes_local\`:

| Archivo | Función |
| --- | --- |
| `chat_fijo_gemini.py` | Cliente de chat fijo por Playwright/CDP 9222. Lee `config_chats` en SQLite en modo solo lectura, normaliza el nombre del proyecto y usa `DOS_AGENTES` como fallback. Reutiliza la pestaña del mismo identificador de chat, ignorando parámetros de idioma; si falta, abre la URL configurada. Envía texto multilínea y devuelve únicamente el contenido de la respuesta nueva cuando termina la generación y permanece estable. |
| `piloto_gemini.py` | Orquesta pasos de `codex exec` en la carpeta del proyecto y revisiones en ese chat. Acepta nombre registrado en `project_brain`, ruta existente o `--folder`. Termina con `[ENTREGA_FINAL]` en línea propia, error o límite de vueltas (4 por defecto, máximo 20). |
| `requirements_chat_fijo.txt` | Dependencia Playwright separada de los requisitos existentes. No requiere descargar un navegador: utiliza el Chrome/Edge ya abierto. |
| `test_chat_fijo_gemini.py` | 15 pruebas locales de selección/fallback y lectura sin escrituras, validación de URL, error de conexión, espera de respuestas, cierre del ciclo, límite de vueltas y cancelación del proceso Codex. No consultan Gemini ni ejecutan Codex real. |
| `CAMBIOS.md` | Este registro de archivos, reglas, uso y comprobaciones. |

Archivo compartido actualizado: `config_compartida\AGENTS.md`. Se documentaron
los nombres **Cascada AG** (4 cuentas de Antigravity, 8765 → 8045) y **Chat Fijo
Gemini** (chat del proyecto, CDP 9222). Se agregó la regla de conservar scripts
funcionales y registrar cambios con commit. Se replicó íntegramente a
`C:\dos_agentes_local\AGENTS.md` y `C:\Users\H_P\.codex\AGENTS.md`.
La copia del directorio raíz sigue excluida por el `.gitignore` existente;
la fuente versionada es `config_compartida\AGENTS.md`.

### Protección y límites

- No se modificaron `bridge_server.py`, `consultar_gemini.py`, `bucle_autonomo.py`,
  la configuración del MCP, el servicio 8765/8045, el panel 8787 ni la base SQLite.
- El cliente usa un bloqueo del sistema operativo por chat para evitar dos
  pilotos simultáneos. Respeta borradores existentes y generaciones en curso.
  Al salir desconecta Playwright sin cerrar pestañas ni el navegador del usuario.
- La conexión tiene tiempo límite; falta de sesión, error de envío o respuesta
  incompleta detienen el ciclo sin reintentar mensajes. Codex tampoco se inicia
  si la conexión, el chat o el editor fallan antes del primer paso.
- Codex utiliza su configuración/autenticación existentes y sandbox
  `workspace-write`. Cada paso tiene un límite de 900 segundos por defecto y se
  detiene también ante Ctrl+C. No se fuerza ningún modelo ni se modifica el MCP.
- Gemini recibe la tarea y hasta los últimos 16000 caracteres del informe de
  Codex. Sus sugerencias no amplían la autorización original. No incluir secretos
  en tareas ni informes. Solo se envía el informe final de Codex, no sus logs.
- Estado, informes y logs se guardan en `.sync-local\chat-fijo\`, ya excluido
  de Git. Las ejecuciones interrumpidas no se reanudan automáticamente.
- Estos módulos se ejecutan por pedido; no se alteró el arranque de Windows ni
  se creó una tarea que inicie el piloto por su cuenta.

### Uso desde PowerShell

```powershell
# Instalar solo si falta Playwright; ya estaba instalado en esta PC (1.64.1).
& C:\dos_agentes_local\.venv\Scripts\python.exe -m pip install -r C:\dos_agentes_local\requirements_chat_fijo.txt

# Prueba de conexión: no abre pestañas ni envía mensajes.
& C:\dos_agentes_local\.venv\Scripts\python.exe C:\dos_agentes_local\chat_fijo_gemini.py --project DOS_AGENTES --check

# Consulta individual al chat registrado (o fallback DOS_AGENTES).
& C:\dos_agentes_local\.venv\Scripts\python.exe C:\dos_agentes_local\chat_fijo_gemini.py --project DOS_AGENTES --message "Revisá este avance: ..."

# Piloto: nombre registrado o carpeta existente; se puede indicar --folder.
& C:\dos_agentes_local\.venv\Scripts\python.exe C:\dos_agentes_local\piloto_gemini.py --project DOS_AGENTES --folder C:\dos_agentes_local --task "Describí la tarea autorizada" --max-turns 4

& C:\dos_agentes_local\.venv\Scripts\python.exe -B -m unittest discover -s C:\dos_agentes_local -p test_chat_fijo_gemini.py -v
```

Si CDP no responde, abrir Chrome/Edge con `--remote-debugging-port=9222` y
un perfil dedicado, por ejemplo `--user-data-dir="%USERPROFILE%\GeminiCDP"`
desde un acceso directo, e iniciar sesión en Gemini en ese perfil. Si se usa
el túnel CDP existente, restablecer ese túnel. El cliente no inicia navegadores
ni cambia perfiles, cuentas, túneles o procesos por su cuenta.

### Verificación de esta entrega

- Pasaron las 15 pruebas automáticas sin llamadas reales a Gemini/Codex.
- Se comprobó que los argumentos usados por el piloto existen en `codex exec --help`.
- La prueba real `chat_fijo_gemini.py --project DOS_AGENTES --check --connect-timeout 3`
  terminó con error controlado: **127.0.0.1:9222 no respondió**. No se enviaron
  mensajes ni se inició Codex. Falta probar envío/respuesta contra una sesión
  Gemini accesible; los selectores pueden requerir un parche si cambia su interfaz.
- Los tres scripts protegidos se verifican con SHA256 y diff de Git antes del commit.

Referencia técnica: [Playwright Python — Browser y conexión CDP](https://playwright.dev/python/docs/api/class-browser).
