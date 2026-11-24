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
nuevas versiones y pueden aparecer varios chats: no fusiona ediciones paralelas.
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

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\dos_agentes_local\scripts\chats\activar_sync_abierto.ps1 -MachineId PC2 -CloudRoot "I:\Mi unidad\CodexSync\live-v1"
```

En PC3 usar `-MachineId PC3`. Ajustar CloudRoot a su ruta real de Drive. Si Python
esta en otra ruta, pasar `-PythonExecutable` con su pythonw.exe.
PC2 y PC3 aun no fueron configuradas ni verificadas fisicamente.
PC1 puede apagarse cuando termine el ciclo Y Drive complete su subida; publicar
archivos en la carpeta local no demuestra su propagacion remota.

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
