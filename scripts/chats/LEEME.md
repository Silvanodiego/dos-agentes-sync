# Chats independientes entre PCs

Cada PC mantiene su propia carpeta `.codex`. Drive transporta sesiones; no se
comparte ni reemplaza la base SQLite activa. Las credenciales no se copian.
PC1 puede apagarse una vez que la subida terminó y Drive propagó los archivos.

`setup_chats.ps1` instala la versión auditada de codexSync sin activar copias.
Ejecutarlo en cada PC con su ruta real de Drive y un `-MachineId` distinto.
Requiere Python 3.14 o posterior; no usar el mismo identificador en dos PCs.
Después, `activar_sync_chats.ps1` registra `CodexChatsSyncCold`: inicio de sesión
y cada diez minutos, con pythonw y sin ventana. No cierra Codex automáticamente.
La tarea solo puede sincronizar con Codex completamente cerrado. Los cambios
descargados aparecen en la próxima apertura. Abrir la app antes de que termine
la copia puede aplazar la sincronización; no equivale a sincronización en vivo.

En PC1, la tarea recibe además la política local `recovery-acceptance-PC1.json`.
Reconoce únicamente los 111 rollouts que ya faltaban: conserva el ZIP de respaldo,
los diez historiales exportados y exige que sus diez continuaciones tengan
rollouts nativos. No inventa las sesiones originales. Nuevos faltantes bloquean
la copia. No copiar esta excepción a otras PCs como si sus bases fueran iguales.

`recuperar_huerfanos.py` exporta los historiales de usuario desde un respaldo
SQLite verificado; `preparar_continuaciones.py` genera contexto y extractos de
relevo. Sus resultados privados están fuera del repositorio, en Drive. Los chats
de continuación tienen identificadores nuevos; los originales se mantienen.

Los conflictos se detienen con `manual_abort`, conservando las dos versiones.
Evitar editar el mismo chat en dos PCs antes de sincronizar. No promete fusionar
automáticamente dos ramas distintas de una conversación.

Estado: `%LOCALAPPDATA%\CodexSync\automatic-sync-status.json`.
Registro: `%LOCALAPPDATA%\CodexSync\logs\automatic-sync.log`.
`waiting_codex_closed` es espera normal; `synchronized` indica copia terminada;
`conflict_preserved`, `core_error` o `blocked` requieren revisión del registro.
Drive debe terminar su propia subida antes de apagar la PC de origen.

Cerrar la ventana puede dejar la app en la bandeja: usar Salir/Quit. Incluso
despues de salir pueden persistir reportadores de fallos `crashpad-handler`.
`limpiar_crashpad_huerfanos.py` comprueba ruta MSIX de Codex, argumentos, arbol
de padres y fechas. Solo retira reportadores sin ancestro activo, observados
como huerfanos durante al menos dos minutos. Los handles se fijan y validan
antes de terminar procesos para evitar confundir PIDs reutilizados. No termina
la aplicacion, servidores, renderizadores ni arboles desconocidos/mixtos.
El control original del core sigue verificando que Codex este cerrado.
Por el periodo de observacion, un cierre puede requerir dos ciclos de tarea.

La prueba local de transferencia de los diez chats de continuación utilizó un
CODEX_HOME separado, sin credenciales ni SQLite original: lectura y reanudación
10/10 correctas, sin inferencia. Falta validar la descarga en las PCs 2 y 3.
