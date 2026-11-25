# Chats independientes con Codex abierto

`sync_chats_abierto.py` replica conversaciones mediante Drive sin cerrar Codex.
Cada PC conserva su perfil local. La tarea `CodexChatsSyncLive` corre sin ventana
al iniciar sesion y cada dos minutos. En PC1 esta activa; `CodexChatsSyncCold`
queda deshabilitada como respaldo. No ejecutar ambas tareas simultaneamente.

El exportador usa backups SQLite y copia lineas completas de los rollouts.
Cada snapshot de base es consistente individualmente; no son una transaccion
conjunta entre bases y archivos. Publica objetos inmutables con SHA256 en
`CodexSync/live-v1/objects` y un manifiesto por PC. No publica bases completas,
configuracion, auth.json ni perfiles de navegador. Los historiales contienen
conversaciones privadas: mantener esta carpeta de Drive privada y fuera de Git.

En destino inserta versiones terminadas con identificadores nuevos, sin
reemplazar bases ni actualizar/eliminar conversaciones existentes. Sus nombres
llevan `[sync PC1]` (o el origen correspondiente). Continuar una copia publica
esa continuacion; las copias intactas no se reexportan. Nuevos avances generan
nuevas versiones. La ascendencia logica permite archivar las versiones anteriores
sin editar sus mensajes, siempre que esten terminadas y no tengan avances propios.
Los avances simultaneos conservan ambas ramas: no fusiona ediciones paralelas.
La actualizacion inmediata del panel de otra PC aun no esta verificada.

Las generaciones pendientes se conservan y se revisan en ciclos posteriores,
sin enviar mensajes ni ejecutar modelos. Los historiales presentes solo en
SQLite se archivan, sin fabricar rollouts: no pueden reanudarse fielmente como
el original. Los diez historiales afectados ya tienen exportacion completa y
diez continuaciones nativas con contexto recuperado. Originales y ZIP de
respaldo se conservan en la carpeta privada de Drive.

## Activacion en PC2 y PC3

Requiere scripts actualizados, Python 3.14+, iniciar sesion en Codex e iniciar un
chat para crear ambas bases nativas. Drive debe sincronizar la misma carpeta.
Usar un MachineId diferente por PC. El activador no requiere cerrar Codex.
`C:\dos_agentes_local\activar_chats_esta_pc.bat` activa la tarea usando el nombre
del equipo/usuario y detecta la carpeta existente CodexSync/live-v1 en Drive.
Si existen varias ubicaciones o Drive no esta montado, informa el error; no
crea una nube distinta ni anuncia exito. El comando siguiente permite elegir
explicitamente la ubicacion y el identificador.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\dos_agentes_local\scripts\chats\activar_sync_abierto.ps1 -MachineId PC2 -CloudRoot "I:\Mi unidad\CodexSync\live-v1"
```

En PC3 usar `-MachineId PC3`. Ajustar CloudRoot a su ruta real de Drive. Si Python
esta en otra ruta, pasar `-PythonExecutable` con su pythonw.exe.
PC2 y PC3 aun no fueron configuradas ni verificadas fisicamente.
PC1 puede apagarse cuando termine el ciclo Y Drive complete su subida; publicar
archivos en la carpeta local no demuestra su propagacion remota.

## Proyectos actuales y futuros

`proyectos_portables.py` descubre en cada ciclo los proyectos nativos y las
asociaciones antiguas del escritorio, incluso proyectos nuevos sin chats.
Solo exporta nombre, raices y asociaciones permitidas; nunca el archivo global
completo. Normaliza los prefijos Windows \\?\ y traslada las rutas relativas a
Drive o al perfil de cada PC. `path-mappings.json`, junto al estado privado,
admite un objeto de prefijos absolutos origen:destino para otras ubicaciones.
Las carpetas deben existir en destino: Drive sincroniza su contenido; este
servicio replica el historial y sus asociaciones, no los archivos del proyecto.
Una carpeta ausente deja el proyecto pendiente, sin asignarlo a otra carpeta.

El registro usa la API nativa project/create y el project_id local de cada PC.
`rutas_historial.py` adapta cwd de session_meta/turn_context en la nueva replica
y recalcula offsets de proyeccion; mantiene el texto de los mensajes y los
originales. Codex puede canonizar la ruta al reanudar. Las reglas de permisos
se conservan; no copia config.toml, cuentas, credenciales ni confianza global.
Los permisos efectivos siguen dependiendo de la politica local de cada equipo.

Limitacion pendiente: la API nativa puede registrar un proyecto sin que el
escritorio abierto lo muestre inmediatamente. Un proyecto temporal creado en
PC1 no aparecio en list_projects; se elimino al finalizar la prueba. No se
sobrescribe .codex-global-state.json mientras la app esta abierta. Falta una
integracion verificada con la barra lateral y la prueba fisica PC1 -> PC2/PC3.
El campo desktop_project_visibility=not_verified informa este limite;
synchronized_live solo confirma el ciclo de transporte/importacion local.

## Estado y pruebas

Estado: `%LOCALAPPDATA%\CodexSync\live-sync-status.json`.
`synchronized_live`: ciclo local terminado, no certifica la subida de Drive.
`partial_live`: conserva objetos pendientes y su causa. Un esquema incompatible
requiere revisar compatibilidad. `blocked`: conserva el error. No sustituye
la prueba de descarga real en otra PC.

`test_sync_chats_abierto.py`: nueve pruebas de offsets/CRLF, idempotencia,
generaciones pendientes, ausencia de rollout, truncado, incompatibilidad,
integridad, importacion entre perfiles abiertos y continuaciones sin ecos.
Las pruebas nativas usan CODEX_HOME separado sin credenciales, mediante
thread/read y thread/resume; no solicitan inferencia ni alteran el perfil activo.
Los scripts anteriores en frio se conservan como respaldo desactivado; el modo
nuevo no depende de limpiar ni terminar procesos de Codex.

`test_proyectos_continuidad.py` y `test_rutas_historial.py` agregan proyectos
futuros, prefijos Windows, carpetas pendientes, ramas concurrentes, archivado
reversible y offsets tras reubicacion. La prueba nativa aislada tambien verifico
thread/read + thread/resume con cwd trasladado a otra raiz y project_id local.
No solicita inferencia ni certifica el refresco de la barra lateral.

## Instalador V8

V8 registra CodexChatsAutoSetup sin ventana cada dos minutos y al login. Cuando
Drive sincroniza la carpeta existente CodexSync/live-v1 y Codex tiene ambas bases
nativas, activa CodexChatsSyncLive y deshabilita el bootstrap. No cierra Codex.
Si falta Drive o la inicializacion/login de Codex, activation-status.json en
LOCALAPPDATA/CodexSync informa pending con la causa; no declara chats sincronizados.
Reinstalar vuelve a comprobar requisitos y registra la misma tarea sin duplicarla.
Los limites de visibilidad de barra lateral y verificacion fisica siguen vigentes.
