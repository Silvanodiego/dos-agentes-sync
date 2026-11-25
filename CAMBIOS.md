# Registro de cambios

## 2026-11-24 - Reparacion V8: formatos nativos distintos y Git local bloqueado

- `scripts/chats/sync_chats_abierto.py`: detecta el indice SQLite con o sin
  historial separado, exporta JSONL, detecta turnos activos en sus eventos e
  importa columnas compatibles usando exclusivamente valores nativos.
  No crea bases de historial faltantes ni inventa campos requeridos. Un modo
  de historial desconocido se informa conservando el contenido.
- `continuidad_chats.py`: conserva antecesores visibles cuando falta el estado
  nativo de turnos. `proyectos_portables.py`: asocia por cwd en instalaciones
  sin tabla de proyectos; no llama APIs de proyectos que esa version no tiene.
- Activadores PowerShell/Python respetan CODEX_HOME, permiten un ejecutable
  Python separado del codigo del worker y ya no exigen thread_history.
- `scripts/chats/reparar_aislado.ps1` y `scripts/crear_reparacion_chats.py`:
  generan un BAT autocontenido con SHA256 y once modulos allowlist, sin datos
  personales. Se instala en LOCALAPPDATA/CodexSync/runner-hash, respalda tareas,
  conserva modulos modificados y verifica una sincronizacion reciente.
  Evita el Git sucio de la instalacion V8; no lo resetea ni lo sobrescribe.
- `REPARACION_V8.md`, `test_formatos_chats.py` y `test_reparacion_chats.py`:
  documentacion, pruebas de formatos, defaults, campos incompatibles, estado
  parcial, checksum, extraccion repetida y sintaxis de PowerShell5.1.
- No se declara soporte de formatos futuros desconocidos ni refresco visual
  de la app verificado. Historias sin rollout y generaciones en curso producen
  estado parcial. La PC destino debe ejecutar el reparador para comprobar su
  formato real; no se verifico remotamente ni se alteraron tareas de PC1.
- bridge_server.py, consultar_gemini.py y bucle_autonomo.py: intactos por SHA256.

## 2026-11-24 - PC 3 v7: instalacion completa de Node sin bloqueo MSI 1603

- `scripts/node_pc3.ps1` instala la distribucion oficial Node24.22.3 x64,
  con npm y npx completos, si no existe una instalacion Node24 funcional.
  Verifica el SHA256 oficial antes de extraer; conserva instalaciones existentes.
  Un runtime local incompleto se renombra como respaldo antes de reinstalar.
- `scripts/instalar_pc3.ps1` utiliza ese modulo, persiste PATH del usuario y
  restaura la prioridad del Node local despues de cada Refresh-Path.
  Continuan npm ci, globales, Build Tools si hacen falta, pip y todos los servicios.
- El empaquetador incluye el ZIP oficial Node como unica excepcion de archivo
  ZIP de runtime; comprueba su hash y conserva todo el ecosistema de v6.
- Version v7 en instalador/manifiesto/inventario y LEEME_PC3_v7.md nuevo.
  `.gitignore` excluye el runtime expandido para evitar subir binarios.
- `scripts/test_node_pc3.ps1`: prueba real aislada de extraccion, node/npm/npx,
  reutilizacion, prioridad tras Refresh-Path y rechazo SHA256. El empaquetador
  exige esta prueba sobre su contenido final sin alterar PATH de PC1.
- Pruebas existentes y verificacion del paquete. El log de MSI de PC3 no es accesible desde PC1:
  no se atribuye causa especifica a 1603 ni se anuncia instalacion remota exitosa.
- Cascada AG fallo con HTTP502; no se reintento la inferencia.
- Modulos Utility/Archive cargados explicitamente: la prueba con PATH reducido
  detecto PSModulePath heredado de PowerShell 7/Codex incompatible con PS5.1;
  se cargan manifests del PSHOME del ejecutable antes de entregar.
- Sin cambios en bridge_server.py, consultar_gemini.py ni bucle_autonomo.py.

## 2026-11-24 - Instalador PC 3 v6: argumentos nativos corregidos

- `scripts/instalar_pc3.ps1`: se elimina ValueFromRemainingArguments de Run y
  se pasan ejecutable/argumentos por nombre. Winget recibe tokens separados;
  Git, pip, npm y Build Tools conservan rutas y valores con espacios.
- `scripts/test_argumentos_instalador_pc3.ps1`: reproduce el fallo v5 (1
  argumento en lugar de 10) con un ejecutable capturador, sin instalar nada.
  Verifica winget, --override como un unico valor, rutas con espacios y errores.
- `instalar.bat`, `scripts/crear_paquete_pc3.py`,
  `scripts/ecosistema_paquete_pc3.py` y `scripts/configurar_pc3.py`: version v6;
  conserva el ecosistema completo y genera ZIP nuevos sin reemplazar v5.
- `LEEME_PC3_v6.md` documenta la version nueva sin modificar la guia v5.
- El empaquetador exige tambien que pase la prueba argv sobre el contenido final.
- Se valida sintaxis PowerShell/TOML e integridad del paquete con
  `instalar.bat -Verificar`; no se ejecuta una instalacion completa en PC 1.
- bridge_server.py, consultar_gemini.py y bucle_autonomo.py permanecen intactos.

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
  con solo esquemas. No importa cuentas ni credenciales Antigravity o perfiles.
  Se incluyen las exportaciones Codex auth_c1/c2 solicitadas, fuera de Git;
  el auth.json activo se crea en destino desde cuenta 1 solo si no existe.
- Startup usa arrancar_todo_oculto.vbs; DosAgentesGitSync registra el flujo
  auto_sync_git oculto cada diez minutos. En PC 1 ambos ya estaban correctos:
  se verificaron sin recrearlos ni reiniciar servicios.
- `agy.bat --version` y `-v` responden agy 1.0.0 sin inferencia. Los adaptadores
  admiten DOS_AGENTES_ROOT; el MCP esta habilitado en la plantilla compartida.
- `scripts/crear_paquete_pc3.py` exporta fuentes versionadas y genera v5 con
  manifiesto, hashes, validacion batch y exclusion de DB/logs/cache/venv,
  node_modules, auth.json, perfiles Chrome y credenciales Antigravity. Copias
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

## 2026-11-23 â€” Chat Fijo Gemini independiente de Cascada AG

Archivos nuevos en `C:\dos_agentes_local\`:

| Archivo | FunciÃ³n |
| --- | --- |
| `chat_fijo_gemini.py` | Cliente de chat fijo por Playwright/CDP 9222. Lee `config_chats` en SQLite en modo solo lectura, normaliza el nombre del proyecto y usa `DOS_AGENTES` como fallback. Reutiliza la pestaÃ±a del mismo identificador de chat, ignorando parÃ¡metros de idioma; si falta, abre la URL configurada. EnvÃ­a texto multilÃ­nea y devuelve Ãºnicamente el contenido de la respuesta nueva cuando termina la generaciÃ³n y permanece estable. |
| `piloto_gemini.py` | Orquesta pasos de `codex exec` en la carpeta del proyecto y revisiones en ese chat. Acepta nombre registrado en `project_brain`, ruta existente o `--folder`. Termina con `[ENTREGA_FINAL]` en lÃ­nea propia, error o lÃ­mite de vueltas (4 por defecto, mÃ¡ximo 20). |
| `requirements_chat_fijo.txt` | Dependencia Playwright separada de los requisitos existentes. No requiere descargar un navegador: utiliza el Chrome/Edge ya abierto. |
| `test_chat_fijo_gemini.py` | 15 pruebas locales de selecciÃ³n/fallback y lectura sin escrituras, validaciÃ³n de URL, error de conexiÃ³n, espera de respuestas, cierre del ciclo, lÃ­mite de vueltas y cancelaciÃ³n del proceso Codex. No consultan Gemini ni ejecutan Codex real. |
| `CAMBIOS.md` | Este registro de archivos, reglas, uso y comprobaciones. |

Archivo compartido actualizado: `config_compartida\AGENTS.md`. Se documentaron
los nombres **Cascada AG** (4 cuentas de Antigravity, 8765 â†’ 8045) y **Chat Fijo
Gemini** (chat del proyecto, CDP 9222). Se agregÃ³ la regla de conservar scripts
funcionales y registrar cambios con commit. Se replicÃ³ Ã­ntegramente a
`C:\dos_agentes_local\AGENTS.md` y `C:\Users\H_P\.codex\AGENTS.md`.
La copia del directorio raÃ­z sigue excluida por el `.gitignore` existente;
la fuente versionada es `config_compartida\AGENTS.md`.

### ProtecciÃ³n y lÃ­mites

- No se modificaron `bridge_server.py`, `consultar_gemini.py`, `bucle_autonomo.py`,
  la configuraciÃ³n del MCP, el servicio 8765/8045, el panel 8787 ni la base SQLite.
- El cliente usa un bloqueo del sistema operativo por chat para evitar dos
  pilotos simultÃ¡neos. Respeta borradores existentes y generaciones en curso.
  Al salir desconecta Playwright sin cerrar pestaÃ±as ni el navegador del usuario.
- La conexiÃ³n tiene tiempo lÃ­mite; falta de sesiÃ³n, error de envÃ­o o respuesta
  incompleta detienen el ciclo sin reintentar mensajes. Codex tampoco se inicia
  si la conexiÃ³n, el chat o el editor fallan antes del primer paso.
- Codex utiliza su configuraciÃ³n/autenticaciÃ³n existentes y sandbox
  `workspace-write`. Cada paso tiene un lÃ­mite de 900 segundos por defecto y se
  detiene tambiÃ©n ante Ctrl+C. No se fuerza ningÃºn modelo ni se modifica el MCP.
- Gemini recibe la tarea y hasta los Ãºltimos 16000 caracteres del informe de
  Codex. Sus sugerencias no amplÃ­an la autorizaciÃ³n original. No incluir secretos
  en tareas ni informes. Solo se envÃ­a el informe final de Codex, no sus logs.
- Estado, informes y logs se guardan en `.sync-local\chat-fijo\`, ya excluido
  de Git. Las ejecuciones interrumpidas no se reanudan automÃ¡ticamente.
- Estos mÃ³dulos se ejecutan por pedido; no se alterÃ³ el arranque de Windows ni
  se creÃ³ una tarea que inicie el piloto por su cuenta.

### Uso desde PowerShell

```powershell
# Instalar solo si falta Playwright; ya estaba instalado en esta PC (1.64.1).
& C:\dos_agentes_local\.venv\Scripts\python.exe -m pip install -r C:\dos_agentes_local\requirements_chat_fijo.txt

# Prueba de conexiÃ³n: no abre pestaÃ±as ni envÃ­a mensajes.
& C:\dos_agentes_local\.venv\Scripts\python.exe C:\dos_agentes_local\chat_fijo_gemini.py --project DOS_AGENTES --check

# Consulta individual al chat registrado (o fallback DOS_AGENTES).
& C:\dos_agentes_local\.venv\Scripts\python.exe C:\dos_agentes_local\chat_fijo_gemini.py --project DOS_AGENTES --message "RevisÃ¡ este avance: ..."

# Piloto: nombre registrado o carpeta existente; se puede indicar --folder.
& C:\dos_agentes_local\.venv\Scripts\python.exe C:\dos_agentes_local\piloto_gemini.py --project DOS_AGENTES --folder C:\dos_agentes_local --task "DescribÃ­ la tarea autorizada" --max-turns 4

& C:\dos_agentes_local\.venv\Scripts\python.exe -B -m unittest discover -s C:\dos_agentes_local -p test_chat_fijo_gemini.py -v
```

Si CDP no responde, abrir Chrome/Edge con `--remote-debugging-port=9222` y
un perfil dedicado, por ejemplo `--user-data-dir="%USERPROFILE%\GeminiCDP"`
desde un acceso directo, e iniciar sesiÃ³n en Gemini en ese perfil. Si se usa
el tÃºnel CDP existente, restablecer ese tÃºnel. El cliente no inicia navegadores
ni cambia perfiles, cuentas, tÃºneles o procesos por su cuenta.

### VerificaciÃ³n de esta entrega

- Pasaron las 15 pruebas automÃ¡ticas sin llamadas reales a Gemini/Codex.
- Se comprobÃ³ que los argumentos usados por el piloto existen en `codex exec --help`.
- La prueba real `chat_fijo_gemini.py --project DOS_AGENTES --check --connect-timeout 3`
  terminÃ³ con error controlado: **127.0.0.1:9222 no respondiÃ³**. No se enviaron
  mensajes ni se iniciÃ³ Codex. Falta probar envÃ­o/respuesta contra una sesiÃ³n
  Gemini accesible; los selectores pueden requerir un parche si cambia su interfaz.
- Los tres scripts protegidos se verifican con SHA256 y diff de Git antes del commit.

Referencia tÃ©cnica: [Playwright Python â€” Browser y conexiÃ³n CDP](https://playwright.dev/python/docs/api/class-browser).

## 2026-11-23 â€” Lanzador de Chrome/Edge y prueba de conexiÃ³n

- **Nuevo `abrir_chrome_gemini.bat`:** detecta Chrome en las ubicaciones de
  instalaciÃ³n habituales y en PATH; si falta, busca Edge. Abre el navegador
  con `--remote-debugging-port=9222`, el perfil dedicado
  `C:\dos_agentes_local\chrome_gemini_profile` y la URL fija
  `https://gemini.google.com/app/ebb372bdb46e6358?hl=es_419`.
  Devuelve error si no encuentra navegador o falla el lanzamiento.
- **`.gitignore`:** agregado `chrome_gemini_profile/` para excluir Ã­ntegramente
  el perfil, incluidas cookies, sesiones y cualquier archivo de cÃ³digo que
  pudiera contener. `git check-ignore` confirmÃ³ la exclusiÃ³n.
- **`CAMBIOS.md`:** agregado este registro. No se creÃ³ ningÃºn ZIP ni se cambiÃ³
  `bridge_server.py`, el MCP, `consultar_gemini.py` o `bucle_autonomo.py`.
- Chrome y Edge estÃ¡n instalados. La revisiÃ³n automÃ¡tica rechazÃ³ el comando
  `Start-Process` que ejecutaba el BAT en segundo plano con el mensaje
  **`blocked by policy`**, sin detallar otro motivo. Ese comando no se ejecutÃ³;
  no se intentÃ³ eludir el bloqueo mediante otra herramienta de lanzamiento.
- `chat_fijo_gemini.py --project DOS_AGENTES --check --connect-timeout 3`
  informÃ³ de forma controlada que 9222 no responde. TambiÃ©n se consultÃ³
  `http://127.0.0.1:9222/json/version` durante hasta 15 segundos.
- La prueba con el mensaje `Prueba de conexiÃ³n desde Chat Fijo Gemini.
  RespondÃ© solo: CONEXION_OK` queda pendiente: no hubo conexiÃ³n CDP, no se
  enviÃ³ ningÃºn mensaje, no se recibiÃ³ una respuesta y no se pudo verificar
  el inicio de sesiÃ³n. No se afirma que se haya abierto una ventana.
- Se verifica el hash SHA256 original de `bridge_server.py` y su diff vacÃ­o
  antes del commit. Solo se incluyen el BAT nuevo, `.gitignore` y este registro.


## 2026-11-23 â€” Carga, STOP, modelos web y arranque condicional

- **`chat_fijo_gemini.py`:** espera `domcontentloaded` y hasta 5 segundos de
  `networkidle` (si la red persistente impide ese estado, exige editor visible,
  habilitado y editable y ausencia de generaciÃ³n). Espera hasta 15 segundos una
  generaciÃ³n anterior, sin cancelarla; estabiliza 2 segundos antes de escribir y
  vuelve a validar editor, URL y STOP. Conserva borradores y no reenvÃ­a errores.
- STOP revisa aria-label, title y texto, excluyendo audio, voz, voice, micrÃ³fono,
  mic, escuchar y listen. Solo devuelve texto de una respuesta nueva con STOP
  ausente y contenido estable durante al menos 3 segundos, sin exigir botÃ³n copiar.
- Abre el selector web si existe y prioriza Pro/Ultra/Advanced, luego Thinking o
  AnÃ¡lisis mÃ¡s profundo/4 Neon, luego Fast/Flash/RÃ¡pido o Ayuda todos los dÃ­as/4
  Hydrogen; descarta opciones deshabilitadas, agotadas o de suscripciÃ³n.
  Si los nombres son desconocidos, conserva el orden del menÃº disponible.
  Confirma la etiqueta seleccionada. `--json-result` agrega modelo y notas al
  resultado; stderr informa MODELO_WEB tambiÃ©n ante errores. No fuerza modelos
  de Cascada AG ni promete disponibilidad posterior al envÃ­o.
- **`sync_y_arrancar.bat`:** chequeo TCP de 1 segundo; llama al lanzador Gemini
  Ãºnicamente si 127.0.0.1:9222 no escucha y conserva el arranque del sincronizador.
- **`scripts/sync_silencioso.vbs`:** el modo startup ahora ejecuta ese BAT sin
  ventana. La entrada existente DosAgentesSync del Registro ya usa este VBS;
  el modo periÃ³dico conserva su comando anterior. No se relanzaron servicios.
- **`test_chat_fijo_gemini.py`:** 17 pruebas aprobadas: incluyen estabilidad sin
  botÃ³n copiar y selecciÃ³n por prioridad/cuota. Pruebas DOM separadas contra el
  navegador existente: 10 casos STOP/audio/oculto y menÃº sintÃ©tico que descarta
  Pro agotado y selecciona AnÃ¡lisis mÃ¡s profundo; todos aprobados. El VBS se
  verificÃ³ sustituyendo temporalmente Run por Echo en un archivo local ignorado;
  el chequeo TCP omite Chrome con 9222 abierto y detecta un puerto cerrado.
- Prueba real solicitada contra DOS_AGENTES con el mensaje exacto
  `Prueba de conexiÃ³n desde Chat Fijo Gemini. RespondÃ© solo: CONEXION_OK`:
  CDP 9222 respondiÃ³. La URL guardada sigue siendo
  `https://gemini.google.com/app/ebb372bdb46e6358?hl=es_419`, pero Gemini la
  redirige a `/app`. Se detuvo antes de seleccionar modelo o enviar el mensaje;
  no hubo respuesta de Gemini ni se sustituyÃ³ la URL de config_chats. No se
  atribuye la redirecciÃ³n a una causa no verificada. La prueba anterior a estos
  parches sÃ­ enviÃ³ el mensaje y agotÃ³ 120 segundos; no se reenviÃ³ automÃ¡ticamente.
- Diff vacÃ­o y SHA256 original conservado en `bridge_server.py`,
  `consultar_gemini.py` y `bucle_autonomo.py`. Sin cambios al MCP ni a las reglas.

Referencia: [Playwright â€” estados de carga](https://playwright.dev/python/docs/api/class-page#page-wait-for-load-state)
y [comprobaciones del editor](https://playwright.dev/python/docs/actionability).


## 2026-11-23 â€” Chat fijo para la cuenta nueva y persistencia automÃ¡tica

- **`abrir_chrome_gemini.bat`:** la URL inicial ahora es
  `https://gemini.google.com/app`, sin el ID de la cuenta anterior. Conserva
  detecciÃ³n de Chrome/Edge, perfil dedicado y CDP 9222.
- **`chat_fijo_gemini.py`:** un proyecto sin URL (fila ausente, NULL, vacÃ­a o
  `/app`) prepara un chat nuevo. Una URL fija que redirige a `/app` antes del
  envÃ­o tambiÃ©n habilita esa creaciÃ³n. Cada proyecto tiene su propio chat;
  deja de heredar la URL de DOS_AGENTES para proyectos no registrados.
  La preparaciÃ³n conserva espera de carga/editor, estabilizaciÃ³n de 2 segundos,
  selecciÃ³n del mejor modelo habilitado, STOP sin audio y respuesta estable 3 s.
- DespuÃ©s de un Ãºnico envÃ­o, reconoce la transiciÃ³n `/app` a `/app/ID` y guarda
  Ãºnicamente una URL fija HTTPS vÃ¡lida en `config_chats`, asociada al proyecto.
  Guarda el ID apenas aparece para no perder el vÃ­nculo si la generaciÃ³n tarda;
  solo devuelve Ã©xito cuando hay respuesta completa y URL persistida. No guarda
  `/app` como URL fija. El resultado JSON incluye `url`, `model` y `response`.
  Login u otra navegaciÃ³n inesperada detienen el flujo sin reenvÃ­o automÃ¡tico.
- Persistencia SQLite acotada al proyecto, conexiÃ³n mode=rw (sin crear bases
  faltantes), transacciÃ³n y comparaciÃ³n de URL previa para no sobrescribir
  cambios de otro proceso. Bloqueo por proyecto desde antes de releer la
  configuraciÃ³n: funciona aunque todavÃ­a no exista URL y aunque cambie el ID.
- **`piloto_gemini.py`:** parche puntual para usar ese bloqueo por proyecto y
  releer la configuraciÃ³n dentro del bloqueo. No cambia la ejecuciÃ³n de Codex
  ni el protocolo de cierre del piloto.
- **`estado_puente.db` (local, excluido de Git):** se limpiÃ³ exclusivamente la
  URL vieja de DOS_AGENTES (`ebb372bdb46e6358`). La prueba real creÃ³ y guardÃ³
  `https://gemini.google.com/app/01a343165a8505af` en esa misma fila. No se
  borraron otras filas ni se cambiÃ³ el esquema. La base y el perfil no se suben.
- **`test_chat_fijo_gemini.py`:** 21 pruebas aprobadas; cubren proyecto nuevo
  sin herencia, persistencia y reutilizaciÃ³n, NULL y `/app`, rechazo de URL
  base/no vÃ¡lida, conflicto concurrente, transiciÃ³n de URL antes/despuÃ©s del
  envÃ­o, login, respuesta estable y cuota/modelos, ademÃ¡s del piloto existente.
- **Prueba real solicitada:** CDP 9222 respondiÃ³. Se enviÃ³ una sola vez
  `Prueba de conexiÃ³n desde Chat Fijo Gemini. RespondÃ© solo: CONEXION_OK`.
  Modelo web confirmado: **Neon**. Respuesta exacta completa: **CONEXION_OK**.
  Se verificÃ³ luego que preparar otra conexiÃ³n reutiliza la URL fija guardada,
  sin enviar otra consulta ni crear otro chat.
- Se conservan los hashes originales y diff vacÃ­o de `bridge_server.py`,
  `consultar_gemini.py` y `bucle_autonomo.py`. No se cambiÃ³ Cascada AG ni el MCP.

## 2026-11-23 â€” Cascada AG y arranque invisible de Windows

- `config_compartida/AGENTS.md`: denominaciÃ³n y cierre obligatorios actualizados
  a Cascada AG 8765; 8765/8045 se llama siempre Cascada AG, nunca Puente.
  Copia idÃ©ntica aplicada a `C:\dos_agentes_local\AGENTS.md` y
  `C:\Users\H_P\.codex\AGENTS.md`. El identificador tÃ©cnico del MCP se conserva.
- Nuevo `abrir_chrome_gemini_oculto.bat`: detecta Chrome y luego Edge, verifica
  TCP 9222 antes de abrir y usa --headless=new, perfil dedicado,
  --no-first-run y --no-default-browser-check. Espera de conexiÃ³n acotada a 15 s.
- Nuevo `arrancar_todo_oculto.vbs`: ejecuta el BAT del navegador y luego
  `sync_y_arrancar.bat` mediante WScript.Shell.Run con ventana 0.
- `sync_y_arrancar.bat`: comprueba 127.0.0.1:9222 y llama al lanzador oculto
  solo si el puerto no estÃ¡ escuchando; mantiene el sincronizador existente.
- Inicio de sesiÃ³n del usuario registrado mediante el acceso directo
  `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DosAgentesInicioOculto.lnk`
  a `wscript.exe //B //Nologo "C:\dos_agentes_local\arrancar_todo_oculto.vbs"`.
  Se retirÃ³ Ãºnicamente la entrada anterior DosAgentesSync del Registro HKCU Run
  para evitar el arranque duplicado. La instalaciÃ³n es local a esta PC.
- VerificaciÃ³n: VBS vÃ¡lido y ambas llamadas con ventana 0; detecciÃ³n y flags
  comprobados mediante lanzamiento simulado; con 9222 abierto el BAT termina
  correctamente sin lanzar otro navegador. Tres AGENTS idÃ©nticos. La sesiÃ³n
  actual de Chrome se conserva; el modo headless queda configurado para el
  prÃ³ximo inicio, sin cerrar la sesiÃ³n existente durante las pruebas.
- `bridge_server.py`, `consultar_gemini.py` y `bucle_autonomo.py` mantienen sus
  hashes originales y diff vacÃ­o; no se modificÃ³ el MCP ni Cascada AG.
# 2026-11-23 - Correccion de alcance del paquete v5 completo

- Recuperado el ecosistema omitido de v4: cinco repos Git con bundles,
  skills propias y actuales, plugins y marketplaces, ScriptsGlobales/modulos_enjambre,
  CLI agy, herramientas .bin y configuraciones sin credenciales.
- Nuevo ensamblador con inventario por componente, plantilla TOML completa portable
  y validacion obligatoria de grupos. Antigravity Manager 0.30.0 incluido como
  NSIS oficial SHA256 verificado, sin copiar node_modules sueltos.
- Instalador restaura el ecosistema, importa .git sin requerir login para el
  primer clon, instala token-saver local y globales npm, y verifica SQLite nativo.
  Carga VCTools/SDK para reintento, conserva progreso visible y fix 404.
- Se mantienen Cascada AG, Chat Fijo Gemini, inicio oculto y tarea de diez minutos.
  No se modificaron bridge_server.py, consultar_gemini.py, bucle_autonomo.py ni respaldos.
- Pruebas: TOML completo y merge sin notify duplicado, exclusiones, bases nuevas
  sin datos privados y preservacion de sesiones existentes; sintaxis Python/PowerShell/JS.


# 2026-11-23 - Autonomia dirigida por Chat Fijo Gemini

- Actualizadas las tres copias de AGENTS.md desde config_compartida: direccion por Chat Fijo Gemini/CDP 9222 y Cascada AG limitada a consultas tecnicas de codigo o auditoria.
- Agregado ciclo autonomo de avance/consulta, excepciones ENTREGA_FINAL y credenciales manuales, y etiqueta de cierre. Se conserva el alcance autorizado y la proteccion de credenciales.
- Documentada equivalencia de --proyecto/--mensaje con los argumentos reales --project/--message, sin modificar chat_fijo_gemini.py.
- bridge_server.py, scripts de respaldo y respaldos existentes se mantienen intactos.

# 2026-11-23 - Consola UTF-8 para Chat Fijo Gemini y piloto

- chat_fijo_gemini.py y piloto_gemini.py reconfiguran stdout/stderr con UTF-8 y errors=replace, tolerando capturadores sin reconfigure, streams cerrados y errores de consola.
- Revisadas todas las operaciones de archivos de texto/JSON: mantienen encoding=utf-8 explicito; el lock binario conserva su modo a+b.
- El entorno del subproceso del piloto fuerza PYTHONIOENCODING=utf-8 y conserva el entorno del sistema.
- Pruebas nuevas: salida de emojis/acentos desde consola cp1252 en ambos modulos, captura sin reconfigure y herencia UTF-8/lectura de salida del piloto. Los 24 tests de test_chat_fijo_gemini.py pasan sin acceder al chat ni ejecutar Codex real.
- Verificados por SHA256 bridge_server.py y ocho scripts/archivos de respaldo: sin cambios.

# 2026-11-23 - Prohibido cerrar solo con diagnostico

- Agregada la regla obligatoria en config_compartida/AGENTS.md y sincronizada en AGENTS.md local y %USERPROFILE%/.codex/AGENTS.md.
- Ante bloqueo o riesgo, consultar al Chat Fijo Gemini para definir plan B; si hace falta decision del usuario, informar causa probable, solucion tecnica con comando/paso exacto y alternativa.
- Verificadas las tres copias identicas y SHA256 de bridge_server.py y respaldos sin cambios.

# 2026-11-24 - Preservacion de chats y preparacion de copias independientes

- Nuevos scripts/chats/setup_chats.ps1, backup_chats.py, coverage_chats.py y paquete_historial.py. Instalan el core auditado codexSync (05084c7f67141105883df7c61a9b3eb9faa19661), respaldan sesiones comprimidas y SQLite con checksums, detectan rollouts faltantes y exportan un archivo portable saneado. No incluyen credenciales, config, settings globales ni remote_control_enrollments en el ZIP portable.
- PC1: core instalado en %LOCALAPPDATA%/CodexSync; config validada con Python 3.14.7. Automatizacion e importacion permanecen desactivadas; no se reemplazaron bases activas ni se cerro Codex.
- Respaldo local verificado: 1153 sesiones y 3 bases, 543750443 bytes. Las bases son snapshots consistentes individualmente; no son una transaccion conjunta con Codex abierto.
- Auditoria: 111 threads sin rollout (10 conversaciones de usuario, 98 revisiones y 3 subagentes). has_user_event=0 NO identifica conversaciones prescindibles.
- Prueba con binario exacto de Desktop y CODEX_HOME temporal sin auth: chat normal thread/read y thread/resume OK (10 turnos); chat sin rollout falla missing source rollout / no rollout found. SQLite conserva contenido, pero no basta para reanudar fielmente los 10. No se crearon historiales sinteticos.
- Comando preparacion otras PCs (ajustar CloudRoot a su unidad Drive): powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\dos_agentes_local\scripts\chats\setup_chats.ps1 -CloudRoot "I:\Mi unidad\CodexSync". Requiere Python 3.14+ y carpeta sync existente. Este comando prepara, NO activa sincronizacion.
- Pendiente decision del usuario: conservar los 10 historiales afectados y continuarlos en chats nuevos, o esperar recuperar sus rollouts originales. No se anuncia sincronizacion completa mientras falten archivos y validacion en PC2/PC3.
- Cascada AG no se modifico. Chat Fijo Gemini no envio consulta: detecto un borrador previo y lo conservo. Segunda auditoria Cascada AG fallo HTTP502; no se reintento inferencia; adaptador agy verificado.
- Verificacion final: 20 tests OK. ZIP portable de 274438483 bytes, 1156 archivos, 1264 threads y 43496 items; SHA256 6635cbfd0c3d7c8741b48419f3dfc0a62e966a07e4908bcab3c81a22485bd695. Copia verificada en I:\Mi unidad\CodexSync\respaldos\PC1-historial-20261124-verificado.zip (pendiente propagacion de Drive). El ZIP es respaldo, no importador. Se corrigio cierre explicito de conexiones SQLite temporales durante la prueba real de exportacion.

# 2026-11-24 - Continuaciones recuperadas y sincronizacion en frio

- Aceptada la opcion de conservar los diez historiales completos y continuarlos con identificadores nuevos, sin reconstruir rollouts ficticios ni alterar los originales. scripts/chats/recuperar_huerfanos.py exporta JSON/TXT verificando las bases del respaldo; preparar_continuaciones.py verifica hashes y genera contexto completo y extractos de relevo.
- Datos privados fuera de Git: I:\Mi unidad\CodexSync\historiales_recuperados\PC1-20261124. Diez chats, 11480 items, 619 turnos; contexto de 2954 mensajes humanos/asistente. Diez continuaciones nativas creadas y finalizadas; correspondencia de identificadores guardada en chats_nuevos.json de esa carpeta.
- Prueba con binario exacto de Desktop, CODEX_HOME independiente, solo diez rollouts, sin auth ni copia de SQLite: thread/read y thread/resume correctos 10/10, sin solicitar inferencia. Informe local en %LOCALAPPDATA%\CodexSync\native-transfer-test\report.json. No equivale a prueba fisica en PC2/PC3.
- Nuevos scripts/chats/sync_chats_cerrado.py y activar_sync_chats.ps1; LEEME.md documenta preparacion de otras PCs, limites y estados. Tarea CodexChatsSyncCold registrada en PC1: inicio de sesion y cada diez minutos mediante pythonw, usuario interactivo sin elevacion, sin solapamientos. No termina procesos ni reemplaza SQLite activa.
- Worker comprueba hashes del core, perfil seguro, cobertura actual y recuperacion historica. Excepcion local explicita para los 111 rollouts ya faltantes, con ZIP/historiales verificados y continuaciones nativas; cualquier faltante nuevo bloquea. Invoca codexSync --apply --unattended --conflict-policy manual_abort: no elimina chats ni resuelve divergencias eligiendo una version silenciosamente.
- Diez tests de scripts/chats/test_sync_chats_cerrado.py pasan: faltantes nuevos, historial alterado, recuperacion ausente, rollout perdido/archivado, bloqueo previo al core, parametros seguros y base WAL cerrada sin SHM. Este ultimo caso se inspecciona mediante copia temporal verificada, sin abrir SQLite ni crear archivos en la fuente. Sintaxis PowerShell validada y tarea real ejecutada: waiting_codex_closed / codigo 3, esperado mientras esta app sigue abierta. Primera copia en frio pendiente del cierre de Codex y propagacion de Drive; PC2/PC3 aun no configuradas ni verificadas.
- Cascada AG audito la estrategia (gemini-4-argon-high); Chat Fijo Gemini sigue bloqueado por borrador previo, conservado sin reenviar. bridge_server.py, consultar_gemini.py, bucle_autonomo.py y las reglas AGENTS.md no se modificaron.

# 2026-11-24 - Reportadores Crashpad huerfanos tras Salir

- Corregido el diagnostico: a las 13:12 el usuario SI habia salido de Codex. Los unicos procesos que bloquearon la copia eran ChatGPT.exe 368/15352/22716; 15352 y 22716 se verificaron como --type=crashpad-handler, con padre original 8672 ausente. El 368 termino antes de poder verificar sus argumentos. La instancia nueva, iniciada 13:20, es independiente.
- Nuevo scripts/chats/limpiar_crashpad_huerfanos.py: clasificacion estricta por ruta WindowsApps/OpenAI.Codex_*/app/ChatGPT.exe, tipo crashpad-handler, ancestros y fechas. Exige dos observaciones con al menos 120 segundos como huerfano; rechaza arboles mixtos, identidades desconocidas, ciclos y reutilizacion de PID. Fija handles y revalida ruta/fecha antes de terminar exclusivamente reportadores huerfanos.
- Parche puntual en sync_chats_cerrado.py para limpiar esos reportadores antes de invocar el core original. No se modifico vendor ni se relajo el control de aplicacion cerrada. Estado agrega orphan_crashpad_removed. LEEME.md explica el posible segundo ciclo de espera.
- Suite ampliada: 17 pruebas OK, incluyendo app activa, otro paquete ChatGPT, arbol mixto, PID reutilizado, ciclos y periodo de gracia sin terminaciones. Prueba real a las 13:34:52: retirados exclusivamente los reportadores huerfanos 15352/22716 tras la gracia; la instancia actual 3548 y sus reportadores 22404/14036 permanecen abiertos. El core conserva waiting_codex_closed hasta salir de esta instancia. Tarea CodexChatsSyncCold activa; primera copia en frio pendiente del cierre real. Scripts protegidos intactos.

# 2026-11-24 - Panel unificado y monitor de bandeja independientes

- Nuevos panel_control.py, tray_monitor.py y monitor_services.py. Panel oscuro en español en 127.0.0.1:8787, actualización JSON cada cinco segundos, proyectos config_chats en SQLite de solo lectura, últimos 25 registros y copia al portapapeles. Comprueba 8765 /health y 8045 /v1/models conjuntamente; identifica el puerto caído. Chrome usa /json/version y /json/list para detectar redirección a accounts.google.com. Git muestra rama, commit, divergencia y cambios locales; fetch limitado cada cinco minutos.
- Acciones POST reales con validación Host/Origin y token de sesión: comprobación Cascada AG, git pull --ff-only, Chrome oculto y login visible mediante BAT existente. Reinicio exclusivo del perfil chrome_gemini_profile, sin cerrar otros perfiles. Registros UTF-8 rotativos y protección básica de secretos en su visualización.
- Bandeja pystray con semáforo, menú en vivo y notificación única por incidente hasta recuperación. Watchdog cada 15 segundos, recuperación solo de 9222 y 8787, máximo una tentativa por servicio cada cinco minutos; no inicia ni reinicia Antigravity Manager ni Cascada AG. Mutex Windows por proceso y bind exclusivo del panel evitan instancias duplicadas. Dependencias pystray 0.19.5 y Pillow 13.0.0 ya instaladas; manifiesto requirements_monitor.txt agregado.
- Parches puntuales en arrancar_todo_oculto.vbs, sync_y_arrancar.bat y scripts/sync_git.py para pythonw sin consola y panel nuevo. El acceso directo DosAgentesInicioOculto existente apunta al VBS. Se detuvo únicamente el panel antiguo panel_web_ag/server.py que ocupaba 8787; su archivo se conserva. Panel y bandeja nuevos están activos; la prueba de doble lanzamiento deja una instancia efectiva de cada uno (más el lanzador del venv).
- Verificación real: HTTP 200 y JSON válido en GET /api/health, /api/status, /api/cascada, /api/chat, /api/git, /api/errors; POST test-cascada y git-pull también 200 y OK. Interfaz verificada con Chrome headless independiente: tres tarjetas, tres enlaces de proyectos, sin errores JavaScript, botón Cascada AG funcional. Seis pruebas automáticas pasan: servicios parciales, login, cooldown por servicio, notificación por incidente, despacho de cuatro botones y bloqueo de peticiones ajenas. Reinicios Chrome se simularon para conservar el borrador existente; una prueba opcional de caída forzada fue rechazada por revisión automática (blocked by policy) y no se ejecutó.
- Cascada AG consultada sin forzar modelo: gemini-4-argon-high. Consulta Chat Fijo Gemini DOS_AGENTES bloqueada por borrador previo de 816 caracteres; se inspeccionó la pestaña sin modificarlo ni reenviar generación. bridge_server.py, consultar_gemini.py y bucle_autonomo.py conservan sus SHA256 originales; configuración Cascada AG y respaldos intactos.

# 2026-11-24 - Sincronizacion de chats con Codex abierto

- Agregados scripts/chats/sync_chats_abierto.py, activar_sync_abierto.ps1 y test_sync_chats_abierto.py. Cambia el transporte a snapshots SQLite online y objetos JSON comprimidos inmutables con SHA256 en Drive/live-v1. Exporta solo tablas de conversaciones y rollouts; no publica bases completas, auth ni configuracion. Snapshots individuales, sin prometer transaccion conjunta entre bases/archivos.
- Importacion por versiones con UUID nuevos, inserciones SQLite bajo sus locks normales y rollout canonico; nunca reemplaza bases ni actualiza/elimina chats locales. Conserva offsets y CRLF; reescribe ambos identificadores de session_meta con igual longitud. Copias terminadas reciben [sync PCx]; nuevas continuaciones se vuelven a exportar, copias intactas no generan eco. No fusiona conversaciones simultaneas. Generaciones incompletas esperan otro ciclo; historiales sin rollout quedan archivados, sin inventar contenido.
- PC1: CodexChatsSyncLive registrada al iniciar sesion y cada dos minutos mediante pythonw, sin ventana, sin cerrar ni terminar Codex. CodexChatsSyncCold deshabilitada y conservada como respaldo. Ejecucion automatica real con LastTaskResult=0 mientras Codex permanece abierto.
- Exportacion local verificada: 56 conversaciones visibles de usuario/continuaciones; 13 versiones reanudables, 42 archivadas solo SQLite y una generacion pendiente. Archivos privados en I:\Mi unidad\CodexSync\live-v1. La propagacion remota de Drive no esta verificada. Los diez historiales recuperados, sus continuaciones y el ZIP previo siguen conservados.
- Nueve pruebas automaticas pasan, incluyendo importacion con bases abiertas, identidad, offsets/CRLF, truncado, integridad, incompatibilidad, continuacion y ausencia de eco. Prueba real con el binario instalado de Codex en CODEX_HOME aislado sin credenciales: 13/13 thread/read y thread/resume correctos, sin inferencia; incluye chats de 346, 23 y 10 turnos. Informe privado: %LOCALAPPDATA%\CodexSync\live-native-test-v3\report.json.
- LEEME.md actualizado con limites y activacion PC2/PC3; esas PCs aun no fueron configuradas ni verificadas. La actualizacion inmediata de su panel tampoco se anuncia como probada. PC1 puede apagarse tras completar la subida de Drive. Este cambio no requiere cerrar Codex.
- Cascada AG audito la implementacion. Chat Fijo Gemini conservo un borrador previo y no envio consulta; no se limpio ni reenvio. bridge_server.py, consultar_gemini.py, bucle_autonomo.py y las tres copias de AGENTS.md se conservaron.


# 2026-11-24 - Asociaciones portables y continuidad de chats con la app abierta

- proyectos_portables.py: catalogo continuo de proyectos nativos y legacy, incluidos proyectos futuros sin chats; nombre/raices/asociaciones permitidas, sin copiar el estado global. Normaliza prefijos Windows \\?\, usa anclas de Drive/perfil y permite mapas privados de prefijos absolutos. Carpeta ausente queda pendiente; no se vincula a una carpeta ajena. Registro nativo mediante project/create, con identificadores locales e idempotencia.
- continuidad_chats.py: identidad logica y ascendencia de versiones. Archiva solo antecesores terminados cuyo historial sigue intacto, conservando sus mensajes/rollouts; generaciones activas y ramas concurrentes quedan visibles. Valida ascendencia antes de hacer visible una replica. No fusiona mensajes paralelos.
- rutas_historial.py: modifica solo cwd de session_meta/turn_context en la nueva replica y recalcula offsets SQLite de la proyeccion. Conserva mensajes y finales CRLF. Rechaza offsets incompatibles sin modificar el original. La prueba nativa detecto y permitio corregir que Codex prioriza cwd del rollout sobre el de la base; soporta rutas con prefijo extendido.
- Parches puntuales en sync_chats_abierto.py para proyectos, continuidad, imports idempotentes tras traslado nativo de rollouts y nombres sin sufijos acumulados. Cierra su propio helper de metadatos incluso al fallar; no cierra Codex. Estado informa exported_projects, desktop_project_visibility=not_verified y local_policy_preserved. No copia configuracion, credenciales, confianza global ni cambia los permisos globales de otra PC.
- activar_sync_abierto.ps1 detecta la carpeta compartida existente en Drive, valida modulos necesarios y conserva identificador automatico unico por equipo/usuario. Nuevo activar_chats_esta_pc.bat para activacion inicial sin escribir comandos; Codex puede permanecer abierto. PC2/PC3 requieren esa activacion y sus carpetas sincronizadas; no se instalaron ni probaron fisicamente desde esta PC.
- Verificacion: 39 ejecuciones de tests correctas (incluye casos heredados repetidos) sobre importacion abierta, proyectos futuros, mapeos, ramas, archivado, ascendencia y offsets. Prueba con binario real instalado, CODEX_HOME aislado sin credenciales: thread/read y thread/resume correctos, proyecto local y cwd reubicado comprobados. Informe privado %LOCALAPPDATA%\CodexSync\native-project-verification.json. Sin inferencia.
- PC1: tarea CodexChatsSyncLive sigue activa cada dos minutos y al iniciar sesion, con Codex abierto. Catalogo exportado: 19 proyectos, 56 conversaciones, 13 versiones reanudables, 42 solo SQLite y una generacion pendiente. Los diez historiales recuperados, continuaciones y respaldos previos se conservan. Publicacion local no certifica propagacion remota de Drive.
- Limite comprobado: un proyecto temporal creado por API nativa no aparecio en list_projects del escritorio abierto; fue eliminado al terminar. Falta integrar/verificar el refresco de la barra lateral y probar PC1 -> PC2/PC3. No se sobrescribio el estado global de la app ni se anuncia solucion integral terminada. LEEME.md explica este limite y la activacion preparada.
- bridge_server.py, consultar_gemini.py y bucle_autonomo.py conservan sus SHA256 originales. AGENTS.md no se modifico. Cascada AG fallo HTTP502 all_models_failed; no se reintento inferencia y se verifico adaptador agy. Chat Fijo Gemini tenia borrador previo conservado, sin reenviar la consulta fallida.


## 2026-11-24 - Instalador V8: conservar scripts diferentes en PC2
- scripts/copiar_paquete_pc.ps1: conserva bridge_server.py, consultar_gemini.py y bucle_autonomo.py existentes aunque difieran del paquete, sin bloquear el resto. Guarda hashes y estado en logs/instalacion_archivos_protegidos.json; no oculta diferencias.
- scripts/instalar_pc3.ps1: usa la copia conservadora y valida sintaxis sin ejecutar los scripts protegidos; advierte que una version local diferente requiere verificar compatibilidad en esa PC.
- scripts/validar_scripts_protegidos.py: comprobacion AST sin importar servicios ni escribir los protegidos.
- scripts/test_copiar_paquete_pc.ps1: prueba destino limpio, identico, divergente y reanudacion preservando hashes y fechas.
- instalar.bat, scripts/crear_paquete_pc3.py y scripts/ecosistema_paquete_pc3.py: version V8 para PC2/PC3; conserva Node24 ZIP y pruebas de argumentos winget; manifiesto y validaciones dentro del empaquetado.
- No se modificaron los tres scripts protegidos. Las pruebas locales no sustituyen ejecutar instalar.bat en PC2; no se da por verificada esa PC.
- Verificacion: prueba real en fixtures limpio/identico/divergente/reanudacion y test de argv winget aprobados; sintaxis AST de los tres protegidos aprobada. Consulta Cascada AG revisada localmente. Chat Fijo no envio consulta: detecto borrador preexistente y lo conservo intacto.

### V8 ampliada: chats, reinstalacion PC3 y condicion GitHub
- scripts/github_pc.ps1: requiere GitHub CLI, comprueba sesion y permiso push al repo; solicita login web solo si falta sesion valida. Configura helper Git sin copiar credenciales. El clone offline del bundle no demostraba autenticacion.
- scripts/instalar_pc3.ps1: comprueba acceso GitHub antes de completar instalacion. Reutiliza Git/Python/Node24/Codex/Manager instalados; pip resuelve solo requisitos faltantes y no actualiza pip por reinstalar; npm local comprueba versiones completas del lockfile + npm ls, y globales omiten versiones ya instaladas. No reinicializa repos existentes ni sustituye DB o auth locales.
- scripts/verificar_npm_instalado.py: comprueba versiones instaladas contra lockfile; faltantes o incorrectas requieren reparar.
- scripts/chats/registrar_activacion_automatica.ps1 y activar_cuando_listo.py: registra activacion silenciosa cada dos minutos/al login. Al estar Drive y bases nativas disponibles, activa CodexChatsSyncLive y deshabilita solo el bootstrap. Si falta Drive o iniciar sesion/primer chat de Codex, deja estado pending con causa en LOCALAPPDATA/CodexSync/activation-status.json; no exige cerrar Codex.
- Paquete incluye sincronizador de chats actuales y proyectos futuros, continuidad y rutas portables. Conserva limites documentados de barra lateral y prueba fisica entre PCs aun pendiente; no garantiza fusion de ramas simultaneas ni historial SQLite original reanudable cuando no hay rollout.
- scripts/test_v8_reinstalacion.py: verifica versiones npm, estado pending, activacion y timeout sin tareas o login reales.
- scripts/verificar_token_saver.py: evita reconstruir token-saver si la version instalada coincide, sin importar/ejecutar su fuente. Pruebas adicionales: 5 casos de reinstalacion/activador, 4 de GitHub, 39 del sincronizador y sintaxis PowerShell 5.1 aprobados.

### 2026-11-24 - V8: detener bucle de rotacion de cuenta Codex
- monitor_cuota.pyw: logs confirmaron intentos automaticos C1 -> C2 repetidos tras fallar el cierre de procesos (21:26 y 21:29). No se confirmo una rotacion exitosa: el monitor informaba C1 restaurada. Causa especifica del cierre pendiente; no se fuerza otro cierre para investigarla con trabajo activo.
- Parche puntual: ante fallo, bloqueo persistente de rotacion automatica en .sync-local/rotacion_cuota.json; reanudacion explicita desde bandeja. Un cierre fallido no escribe auth.json ni lanza otra instancia de Codex. El estado corrupto tambien bloquea por seguridad.
- Deteccion de actividad incluye state/thread_history SQLite y WAL, ademas de rollouts. Se desactiva limpieza antigua que borraba historiales: el monitor conserva todos los chats.
- PC1: detenido solo el monitor de cuota y creado bloqueo preventivo; se reinicia el monitor actualizado para mostrar cuotas sin rotar. No se cierran Codex ni servicios, ni se cambian credenciales.
- scripts/test_rotacion_cuota.py: cinco pruebas sin procesos ni credenciales reales; fallo de cierre sin escritura/reinicio, bloqueo persistente y reanudacion, SQLite activo y preservacion de historiales. scripts/crear_paquete_pc3.py ejecuta tambien estas pruebas antes de comprimir V8. Tres scripts protegidos conservan sus hashes originales.
- Verificacion del ZIP detecto PSModulePath heredado de PowerShell 7 en pruebas PowerShell 5.1 (Get-FileHash no disponible). El constructor ahora usa rutas de modulos Windows PowerShell, igual que instalar.bat; se repite la verificacion completa antes de entregar.
- Test de rotacion aisla tambien logging: no crea archivos fuera del manifiesto ni escribe fallos simulados en el registro del monitor real.
- Empaquetador desactiva bytecode en subprocesos de prueba (PYTHONDONTWRITEBYTECODE) para no agregar __pycache__ fuera del manifiesto; diferencias de contenido informan ahora nombres exactos antes de entregar.

### 2026-11-24 - Revision tras instalacion V8 sin chats visibles
- PC1: solo se observa PC1.json en el transporte compartido; no hay evidencia de ejecucion ni subida de PC2/PC3. Error temporal WAL_WITHOUT_SHM a las 22:01 se recupero en la siguiente ejecucion: 58 chats/19 proyectos exportados, cero objetos pendientes a las 22:03. La subida efectiva a Google Drive y el estado remoto siguen sin verificar.
- scripts/chats/activar_cuando_listo.py: no deshabilita el bootstrap ni marca activated por registrar una tarea. Exige resultado synchronized_live nuevo de la primera ejecucion; status ausente, antiguo, parcial o bloqueado conserva pending y su causa.
- scripts/test_v8_reinstalacion.py: 7 pruebas aprobadas, incluyendo registro exitoso con worker fallido y rechazo de resultados antiguos/parciales/bloqueados.
- revisar_chats_v8.bat y scripts/chats/diagnosticar_sync.ps1: actualizacion ff-only y reactivacion sin cerrar Codex, con informe legible de tareas, errores, bases (solo nombres) y manifiestos Drive; no lee credenciales ni contenido de chats.

### 2026-11-25 - Reglas permanentes y modulo temporal de Codex
- Alta de `.agents\rules\workspace-rules.md` como base permanente para Antigravity IDE.
- Alta de `codex_temporal\` (`auditar_diff.ps1`, `correr_tests.ps1`) y `desactivar_codex.ps1` para desmontaje limpio de Codex a fin de mes.
- 2026-11-25: Respaldo de AGENTS.md anterior en `config_backups/AGENTS_viejo_cascada_20261125.md`; reglas limpias unificadas en `AGENTS.md` y `config_compartida/AGENTS.md`, eliminando la carpeta duplicada `.agents/`.
