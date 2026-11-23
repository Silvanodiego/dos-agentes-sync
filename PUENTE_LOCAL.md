# Ejecucion local autorizada
Usar agy.bat --exec diagnostico (o --exec-py diagnostico).
Solo se ejecutan tareas registradas en ~/.antigravity-agent/local_bridge_tasks.json.
Cada entrada fija argv (lista sin shell), cwd y timeout (maximo 90 segundos).
Registrar un script exige editar ese archivo local conscientemente; HTTP no permite registrar ni cambiar argumentos.
El token esta en local_bridge_token; no compartirlo. El puente escucha solo en loopback.
La ejecucion local no equivale a una auditoria de Antigravity ni permite eludir permisos de las herramientas.
Los fallos del modelo, del proceso y los timeouts devuelven errores reales.
