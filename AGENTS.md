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
