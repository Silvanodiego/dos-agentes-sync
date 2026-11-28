# REGLA OBLIGATORIA DE FLUJO (NO NEGOCIABLE)

- En TODOS los turnos, salvo que el usuario escriba literalmente `sin puente`:
  1. Delegá análisis, diagnósticos o borradores a `mcp__antigravity_bridge__antigravity_ask`.
  2. Si encontrás un bloqueo (error de autenticación, comando fallido o archivo faltante), NO frenes ni le pidas al usuario que lo haga a mano sin antes: (a) buscar credenciales, llaves, configs o APIs alternativas en el entorno local, y (b) consultar a `mcp__antigravity_bridge__gemini_ask` pasándole el error exacto para pedir una vía alternativa y ejecutarla.
  3. Antes de entregar la respuesta final, validá con `mcp__antigravity_bridge__gemini_ask` que el objetivo esté resuelto.
  4. Cerrá SIEMPRE con los IDs exactos devueltos por las herramientas: `[Flujo: AG=<call_id o omitido> | Gemini=<call_id o omitido>]`. Prohibido inventar IDs o poner `ok` sin `call_id`.

# Reglas Permanentes del Workspace (Antigravity IDE)

## 1. Integridad y archivos existentes
- No sobrescribir ni borrar scripts o módulos que ya funcionan sin confirmación explícita.
- Registrar cambios relevantes en `CAMBIOS.md`.
- No agregar puentes custom, wrappers innecesarios ni archivos de adorno.

## 2. Seguridad y credenciales
- Nunca enviar contraseñas, tokens, claves API ni archivos de sesión a chats o modelos.
- Respetar `.gitignore` siempre. Nunca ejecutar `git add -f` sobre credenciales, perfiles o sesiones.

## 3. Verificación real y entorno Windows
- Usar UTF-8 seguro en consola y guardar archivos en UTF-8 sin BOM.
- Verificar cada cambio con salida real de comandos antes de dar una tarea por terminada.
- No ocultar errores ni inventar resultados.

## 4. Prohibido cerrar solo con diagnóstico
Si una tarea se traba o requiere frenar por riesgo (permisos, red, datos, hardware), cerrar siempre con:
1. Causa probable en 1 línea.
2. Solución técnica recomendada con comando o paso exacto.
3. Una alternativa si esa no aplica.

## 5. Sincronización Git (PC 1, PC 2, PC 3)
- Trabajar desde `C:\dos_agentes_local`.
- Al terminar cambios aprobados: verificar estado, hacer `git add` respetando `.gitignore`, `git commit` breve y `git push`.
- Si falla la red o el remoto, conservar el commit local e informar el pendiente.

## Continuidad automática entre PCs (sin sincronizar chats)

- Al iniciar una tarea en un chat nuevo, leé primero `ESTADO.md` en la raíz del proyecto actual si existe.
- Al terminar cualquier tarea que modifique archivos (sin esperar a que el usuario diga "terminamos"), sobrescribí `ESTADO.md` en la raíz del proyecto actual en UTF-8 sin BOM (máximo 25 líneas: fecha, qué quedó hecho/verificado, qué falló o quedó bloqueado, y próximo paso exacto).
- Si el proyecto tiene Git, incluí `ESTADO.md` en el commit/push. No actualices `ESTADO.md` en consultas de solo lectura.
- Solo si trabajás en una carpeta local sin Git ni sincronización en la nube, guardá el respaldo en `C:\dos_agentes_local\project_states\ESTADO_<PROYECTO>.md`.
