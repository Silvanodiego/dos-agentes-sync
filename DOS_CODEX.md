# Dos cuentas Codex en Windows

Comando global instalado en PATH: equipo --project "I:\Mi unidad\Claude\PROYECTO" --task "Descripcion del trabajo".
En el chat, las instrucciones globales indican al coordinador detectar el proyecto y ejecutar el circuito con el pedido del usuario. No hace falta mencionar herramientas ni escribir este comando. Es una instruccion del asistente, no un servicio que intercepte todos los chats. El comando manual sigue disponible para diagnostico.

Reparto automatico instalado:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\dos_codex.ps1 tarea --project "I:\Mi unidad\Claude\PROYECTO" --task "Descripcion del trabajo"

El coordinador planifica, el ejecutor implementa en una copia local y el coordinador revisa. Antigravity y Puente participan al inicio y al cierre. Si fallan se registra FAILED, sin aprobaciones inventadas. Cada trabajo guarda estado, logs y resultado en C:\dos_agentes_local\codex_jobs. Cada etapa Codex guarda un JSON con perfil, huella SHA256 del identificador de cuenta (sin credenciales), horarios, codigo de salida y hash de su respuesta. REVIEWED exige revision aprobada y COMPLETO_100% explicito de ambos auditores; REQUIRES_CHANGES requiere correcciones. El script conserva los cambios en una copia; el coordinador del chat debe revisar diferencias, integrar los cambios autorizados al original y probarlos antes de entregar. No constituye aislamiento de seguridad para codigo hostil; utiliza los permisos sandbox de Codex.

Coordinador: perfil existente C:\Users\H_P\.codex, conservado sin migrar.
Ejecutor: perfil independiente C:\Users\H_P\.cx\ejecutor.
Gestor instalado: multi-codex 0.15.0. No se copiaron credenciales.

Desde esta carpeta:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\dos_codex.ps1 estado
    powershell -NoProfile -ExecutionPolicy Bypass -File .\dos_codex.ps1 coordinador
    powershell -NoProfile -ExecutionPolicy Bypass -File .\dos_codex.ps1 ejecutor
    powershell -NoProfile -ExecutionPolicy Bypass -File .\dos_codex.ps1 login-ejecutor

Ejecutor autenticado. Prueba real del 20/11/2026: codex-ejecutor exec en sandbox read-only devolvio OK_SEGUNDO_CODEX_REAL con codigo 0 (gpt-6.1-terra). Comparacion local de identidades: ambos perfiles autenticados y cuentas distintas, sin mostrar credenciales.
Usar una carpeta de trabajo distinta para cada tarea con escritura concurrente.
Los perfiles no comparten autenticacion, sesiones ni configuracion.
El lanzador del coordinador restaura CODEX_HOME al terminar.

Agent Orchestrator 0.7.1 fue probado y retirado: importa fcntl, inexistente en Windows nativo.
No se instalo Claude Code.
Las cuatro cuentas del proxy figuran activas en SQLite; eso no demuestra cuatro trabajadores independientes.
El proxy lista modelos pero la inferencia debe verificarse antes de usarlo.

Estado de validacion 20/11/2026: prueba completa en C:\dos_agentes_local\codex_jobs\20261120_151806_938ba4ef. El segundo Codex (perfil ejecutor, huella 7137b9de10edb5e6) corrigio sumar.py y ejecuto siete pruebas con salida 0. El coordinador reviso y repitio las siete pruebas. Antigravity y Puente respondieron COMPLETO_100%; estado REVIEWED. El cambio fue integrado al proyecto de prueba original y las siete pruebas volvieron a pasar con salida 0 (integration.json: INTEGRATED_AND_TESTED). Los registros de cada etapa, audit_verify.txt y status.json acreditan esta ejecucion; una revision externa incompleta bloquea REVIEWED.
