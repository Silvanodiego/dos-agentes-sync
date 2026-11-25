# Reparacion de chats V8

El archivo `reparar_chats_v8.bat` se genera con
`python scripts/crear_reparacion_chats.py --output <destino>` y se ejecuta con
doble clic en la PC instalada. No requiere cerrar Codex ni actualizar el Git
local antes de ejecutarlo. Incluye solo once modulos de conversacion y tareas;
no transporta chats, autenticacion, perfiles de Chrome ni configuracion de cuentas.

Extrae su contenido verificado por SHA256 a
`%LOCALAPPDATA%\CodexSync\runner-<hash>`, conserva cualquier modulo local
modificado y registra los workers desde esa ubicacion. Reutiliza el Python de
`C:\dos_agentes_local\.venv`, respalda las tareas anteriores en `task-backups`
y exige un resultado reciente del worker antes de anunciar exito.

Formatos contemplados: indice nativo `state_<version>.sqlite` con JSONL, con
o sin `thread_history_<version>.sqlite`. Utiliza las columnas y valores
predeterminados reales de cada instalacion; nunca crea una base de historial
ausente ni inventa valores de columnas obligatorias. Respeta `CODEX_HOME`.
En instalaciones sin tabla de proyectos conserva la asociacion mediante cwd;
la aparicion de proyectos en la interfaz no se da por verificada.

No constituye soporte universal de cualquier version futura de Codex. Sin un
indice nativo conocido, con varias bases ambiguas, con campos requeridos sin
equivalencia o con un modo de historial desconocido se conserva el contenido
y se informa el motivo exacto. Los chats solo SQLite sin rollout y las
generaciones pendientes se conservan en Drive y producen estado parcial,
no se anuncian como importados. No se fusionan ediciones simultaneas.

Informe: `%LOCALAPPDATA%\CodexSync\reparacion-chats-v8.txt`.
Estados: `activation-status.json` y `live-sync-status.json` en esa carpeta.
El archivo BAT no resuelve ni altera los cambios del repositorio instalado:
los evita para que no bloqueen esta reparacion. Los scripts protegidos quedan
intactos. Para deshacer el cambio de tareas se pueden restaurar sus XML con
`Register-ScheduledTask -TaskName <nombre> -Xml (Get-Content <respaldo.xml> -Raw)`.
