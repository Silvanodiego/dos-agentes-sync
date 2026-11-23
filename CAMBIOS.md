# Registro de cambios

## 2026-11-23 - Instalador limpio PC 3 v5

- Se completo el destino antes inexistente `scripts/instalar_pc3.ps1` de
  `instalar.bat`: seis etapas visibles, integridad SHA256 antes de instalar,
  elevacion, requisitos mediante winget, pip, npm ci y reintento con VCTools.
- Node.js 24 se selecciona por su identificador winget `OpenJS.NodeJS.24`.
  Antigravity Manager se resuelve desde la API oficial de releases y se valida
  contra su digest SHA256; se elimina la dependencia de URLs fijas que daban 404.
- `scripts/configurar_pc3.py` expande USERPROFILE despues de parsear TOML,
  conserva notify y MCPs existentes, rechaza duplicados y habilita
  antigravity_bridge. Prepara AGENTS Cascada AG, adaptadores y bases nuevas
  con solo esquemas. No importa cuentas, perfiles ni credenciales.
- Startup usa arrancar_todo_oculto.vbs; DosAgentesGitSync registra el flujo
  auto_sync_git oculto cada diez minutos. En PC 1 ambos ya estaban correctos:
  se verificaron sin recrearlos ni reiniciar servicios.
- `agy.bat --version` y `-v` responden agy 1.0.0 sin inferencia. Los adaptadores
  admiten DOS_AGENTES_ROOT; el MCP esta habilitado en la plantilla compartida.
- `scripts/crear_paquete_pc3.py` exporta fuentes versionadas y genera v5 con
  manifiesto, hashes, validacion batch y exclusion de DB/logs/cache/venv,
  node_modules, auth, perfiles Chrome y credenciales Antigravity. Copias
  identicas en Escritorio y Drive. LEEME_PC3_v5.md documenta autenticaciones.
- Pruebas: TOML portable y fusion conservadora, rechazo de notify duplicado,
  idempotencia y preservacion de DB/token existentes, exclusiones, lockfile,
  sintaxis Python/PowerShell y verificacion real de instalar.bat -Verificar.
- La prueba real detecto herencia de PSModulePath de PowerShell 7 al lanzar
  Windows PowerShell 5.1 desde Python. instalar.bat usa rutas de modulos 5.1
  solo dentro de setlocal, evitando que falte Get-FileHash sin cambiar el sistema.
- No se modificaron bridge_server.py, consultar_gemini.py, bucle_autonomo.py
  ni los respaldos. Cascada AG devolvio HTTP 502 en la consulta de analisis;
  no se reintento inferencia y las comprobaciones fueron locales.

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

## 2026-11-23 — Lanzador de Chrome/Edge y prueba de conexión

- **Nuevo `abrir_chrome_gemini.bat`:** detecta Chrome en las ubicaciones de
  instalación habituales y en PATH; si falta, busca Edge. Abre el navegador
  con `--remote-debugging-port=9222`, el perfil dedicado
  `C:\dos_agentes_local\chrome_gemini_profile` y la URL fija
  `https://gemini.google.com/app/ebb372bdb46e6358?hl=es_419`.
  Devuelve error si no encuentra navegador o falla el lanzamiento.
- **`.gitignore`:** agregado `chrome_gemini_profile/` para excluir íntegramente
  el perfil, incluidas cookies, sesiones y cualquier archivo de código que
  pudiera contener. `git check-ignore` confirmó la exclusión.
- **`CAMBIOS.md`:** agregado este registro. No se creó ningún ZIP ni se cambió
  `bridge_server.py`, el MCP, `consultar_gemini.py` o `bucle_autonomo.py`.
- Chrome y Edge están instalados. La revisión automática rechazó el comando
  `Start-Process` que ejecutaba el BAT en segundo plano con el mensaje
  **`blocked by policy`**, sin detallar otro motivo. Ese comando no se ejecutó;
  no se intentó eludir el bloqueo mediante otra herramienta de lanzamiento.
- `chat_fijo_gemini.py --project DOS_AGENTES --check --connect-timeout 3`
  informó de forma controlada que 9222 no responde. También se consultó
  `http://127.0.0.1:9222/json/version` durante hasta 15 segundos.
- La prueba con el mensaje `Prueba de conexión desde Chat Fijo Gemini.
  Respondé solo: CONEXION_OK` queda pendiente: no hubo conexión CDP, no se
  envió ningún mensaje, no se recibió una respuesta y no se pudo verificar
  el inicio de sesión. No se afirma que se haya abierto una ventana.
- Se verifica el hash SHA256 original de `bridge_server.py` y su diff vacío
  antes del commit. Solo se incluyen el BAT nuevo, `.gitignore` y este registro.


## 2026-11-23 — Carga, STOP, modelos web y arranque condicional

- **`chat_fijo_gemini.py`:** espera `domcontentloaded` y hasta 5 segundos de
  `networkidle` (si la red persistente impide ese estado, exige editor visible,
  habilitado y editable y ausencia de generación). Espera hasta 15 segundos una
  generación anterior, sin cancelarla; estabiliza 2 segundos antes de escribir y
  vuelve a validar editor, URL y STOP. Conserva borradores y no reenvía errores.
- STOP revisa aria-label, title y texto, excluyendo audio, voz, voice, micrófono,
  mic, escuchar y listen. Solo devuelve texto de una respuesta nueva con STOP
  ausente y contenido estable durante al menos 3 segundos, sin exigir botón copiar.
- Abre el selector web si existe y prioriza Pro/Ultra/Advanced, luego Thinking o
  Análisis más profundo/4 Neon, luego Fast/Flash/Rápido o Ayuda todos los días/4
  Hydrogen; descarta opciones deshabilitadas, agotadas o de suscripción.
  Si los nombres son desconocidos, conserva el orden del menú disponible.
  Confirma la etiqueta seleccionada. `--json-result` agrega modelo y notas al
  resultado; stderr informa MODELO_WEB también ante errores. No fuerza modelos
  de Cascada AG ni promete disponibilidad posterior al envío.
- **`sync_y_arrancar.bat`:** chequeo TCP de 1 segundo; llama al lanzador Gemini
  únicamente si 127.0.0.1:9222 no escucha y conserva el arranque del sincronizador.
- **`scripts/sync_silencioso.vbs`:** el modo startup ahora ejecuta ese BAT sin
  ventana. La entrada existente DosAgentesSync del Registro ya usa este VBS;
  el modo periódico conserva su comando anterior. No se relanzaron servicios.
- **`test_chat_fijo_gemini.py`:** 17 pruebas aprobadas: incluyen estabilidad sin
  botón copiar y selección por prioridad/cuota. Pruebas DOM separadas contra el
  navegador existente: 10 casos STOP/audio/oculto y menú sintético que descarta
  Pro agotado y selecciona Análisis más profundo; todos aprobados. El VBS se
  verificó sustituyendo temporalmente Run por Echo en un archivo local ignorado;
  el chequeo TCP omite Chrome con 9222 abierto y detecta un puerto cerrado.
- Prueba real solicitada contra DOS_AGENTES con el mensaje exacto
  `Prueba de conexión desde Chat Fijo Gemini. Respondé solo: CONEXION_OK`:
  CDP 9222 respondió. La URL guardada sigue siendo
  `https://gemini.google.com/app/ebb372bdb46e6358?hl=es_419`, pero Gemini la
  redirige a `/app`. Se detuvo antes de seleccionar modelo o enviar el mensaje;
  no hubo respuesta de Gemini ni se sustituyó la URL de config_chats. No se
  atribuye la redirección a una causa no verificada. La prueba anterior a estos
  parches sí envió el mensaje y agotó 120 segundos; no se reenvió automáticamente.
- Diff vacío y SHA256 original conservado en `bridge_server.py`,
  `consultar_gemini.py` y `bucle_autonomo.py`. Sin cambios al MCP ni a las reglas.

Referencia: [Playwright — estados de carga](https://playwright.dev/python/docs/api/class-page#page-wait-for-load-state)
y [comprobaciones del editor](https://playwright.dev/python/docs/actionability).


## 2026-11-23 — Chat fijo para la cuenta nueva y persistencia automática

- **`abrir_chrome_gemini.bat`:** la URL inicial ahora es
  `https://gemini.google.com/app`, sin el ID de la cuenta anterior. Conserva
  detección de Chrome/Edge, perfil dedicado y CDP 9222.
- **`chat_fijo_gemini.py`:** un proyecto sin URL (fila ausente, NULL, vacía o
  `/app`) prepara un chat nuevo. Una URL fija que redirige a `/app` antes del
  envío también habilita esa creación. Cada proyecto tiene su propio chat;
  deja de heredar la URL de DOS_AGENTES para proyectos no registrados.
  La preparación conserva espera de carga/editor, estabilización de 2 segundos,
  selección del mejor modelo habilitado, STOP sin audio y respuesta estable 3 s.
- Después de un único envío, reconoce la transición `/app` a `/app/ID` y guarda
  únicamente una URL fija HTTPS válida en `config_chats`, asociada al proyecto.
  Guarda el ID apenas aparece para no perder el vínculo si la generación tarda;
  solo devuelve éxito cuando hay respuesta completa y URL persistida. No guarda
  `/app` como URL fija. El resultado JSON incluye `url`, `model` y `response`.
  Login u otra navegación inesperada detienen el flujo sin reenvío automático.
- Persistencia SQLite acotada al proyecto, conexión mode=rw (sin crear bases
  faltantes), transacción y comparación de URL previa para no sobrescribir
  cambios de otro proceso. Bloqueo por proyecto desde antes de releer la
  configuración: funciona aunque todavía no exista URL y aunque cambie el ID.
- **`piloto_gemini.py`:** parche puntual para usar ese bloqueo por proyecto y
  releer la configuración dentro del bloqueo. No cambia la ejecución de Codex
  ni el protocolo de cierre del piloto.
- **`estado_puente.db` (local, excluido de Git):** se limpió exclusivamente la
  URL vieja de DOS_AGENTES (`ebb372bdb46e6358`). La prueba real creó y guardó
  `https://gemini.google.com/app/01a343165a8505af` en esa misma fila. No se
  borraron otras filas ni se cambió el esquema. La base y el perfil no se suben.
- **`test_chat_fijo_gemini.py`:** 21 pruebas aprobadas; cubren proyecto nuevo
  sin herencia, persistencia y reutilización, NULL y `/app`, rechazo de URL
  base/no válida, conflicto concurrente, transición de URL antes/después del
  envío, login, respuesta estable y cuota/modelos, además del piloto existente.
- **Prueba real solicitada:** CDP 9222 respondió. Se envió una sola vez
  `Prueba de conexión desde Chat Fijo Gemini. Respondé solo: CONEXION_OK`.
  Modelo web confirmado: **Neon**. Respuesta exacta completa: **CONEXION_OK**.
  Se verificó luego que preparar otra conexión reutiliza la URL fija guardada,
  sin enviar otra consulta ni crear otro chat.
- Se conservan los hashes originales y diff vacío de `bridge_server.py`,
  `consultar_gemini.py` y `bucle_autonomo.py`. No se cambió Cascada AG ni el MCP.

## 2026-11-23 — Cascada AG y arranque invisible de Windows

- `config_compartida/AGENTS.md`: denominación y cierre obligatorios actualizados
  a Cascada AG 8765; 8765/8045 se llama siempre Cascada AG, nunca Puente.
  Copia idéntica aplicada a `C:\dos_agentes_local\AGENTS.md` y
  `C:\Users\H_P\.codex\AGENTS.md`. El identificador técnico del MCP se conserva.
- Nuevo `abrir_chrome_gemini_oculto.bat`: detecta Chrome y luego Edge, verifica
  TCP 9222 antes de abrir y usa --headless=new, perfil dedicado,
  --no-first-run y --no-default-browser-check. Espera de conexión acotada a 15 s.
- Nuevo `arrancar_todo_oculto.vbs`: ejecuta el BAT del navegador y luego
  `sync_y_arrancar.bat` mediante WScript.Shell.Run con ventana 0.
- `sync_y_arrancar.bat`: comprueba 127.0.0.1:9222 y llama al lanzador oculto
  solo si el puerto no está escuchando; mantiene el sincronizador existente.
- Inicio de sesión del usuario registrado mediante el acceso directo
  `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DosAgentesInicioOculto.lnk`
  a `wscript.exe //B //Nologo "C:\dos_agentes_local\arrancar_todo_oculto.vbs"`.
  Se retiró únicamente la entrada anterior DosAgentesSync del Registro HKCU Run
  para evitar el arranque duplicado. La instalación es local a esta PC.
- Verificación: VBS válido y ambas llamadas con ventana 0; detección y flags
  comprobados mediante lanzamiento simulado; con 9222 abierto el BAT termina
  correctamente sin lanzar otro navegador. Tres AGENTS idénticos. La sesión
  actual de Chrome se conserva; el modo headless queda configurado para el
  próximo inicio, sin cerrar la sesión existente durante las pruebas.
- `bridge_server.py`, `consultar_gemini.py` y `bucle_autonomo.py` mantienen sus
  hashes originales y diff vacío; no se modificó el MCP ni Cascada AG.
