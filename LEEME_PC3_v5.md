# Migracion Codex Limpia v5

Extraer la carpeta completa en una ruta local y ejecutar instalar.bat.
El instalador muestra seis etapas en vivo, valida SHA256 antes de instalar,
solicita Administrador, instala requisitos faltantes y prepara C:\dos_agentes_local.
Necesita Internet, winget (App Installer de Microsoft) y acceso al repositorio
https://github.com/Silvanodiego/dos-agentes-sync.git, rama main.
Si el repositorio requiere autenticacion, iniciar sesion con Git Credential Manager.
No se transfieren credenciales de GitHub en el paquete.

Python 3.11-3.14, Git y Node.js LTS 24; pip instala los tres requirements.
npm ci respeta package-lock.json. Ante un fallo instala VCTools/Windows SDK
y reintenta una vez. Los errores finales son visibles y no se anuncian como exito.
No se instala token-saver desde PyPI. Codex CLI se instala con npm si falta.
Codex Desktop se instala por separado desde Microsoft Store si se quiere su GUI.

Antigravity Manager: instalador oficial NSIS resuelto desde releases/latest
de Draculabo/AntigravityManager, con comprobacion SHA256 de GitHub. No se usan
URLs inventadas de una version fija. El programa se instala en AntigravityManager.
La PC 3 obtiene claves locales nuevas; hay que volver a autenticar las cuentas
en Antigravity Manager, Codex y Gemini (las credenciales DPAPI no son portables).
El monitor muestra cuota solo despues de cargar localmente auth_c1.json y
auth_c2.json de las cuentas autenticadas en esa PC; no vienen dentro de este ZIP.

La plantilla TOML contiene %USERPROFILE%: el instalador expande los valores
parseados y escribe rutas reales del usuario nuevo, porque TOML no expande
variables de entorno. Conserva un notify ya existente sin duplicarlo, valida
con tomllib y habilita el MCP antigravity_bridge. Rechaza TOML previo invalido.

Cascada AG: bridge_server.py (8765) -> Antigravity Manager (8045).
Chat Fijo Gemini: chat_fijo_gemini.py + piloto_gemini.py -> Chrome/Edge CDP 9222,
separado de Cascada AG. Abrir abrir_chrome_gemini.bat para autenticar Gemini.
Se crean bases vacias a partir del esquema, sin historial ni URL de chats privados.
El panel escucha en 8787. ScriptsGlobales recibe agy.bat y antigravity_mcp.bat.

Inicio: DosAgentesInicioOculto.lnk ejecuta arrancar_todo_oculto.vbs mediante
wscript; tarea DosAgentesGitSync (auto_sync_git) cada diez minutos, oculta,
ejecuta scripts/sync_silencioso.vbs periodic, el mismo flujo de auto_sync_git.bat.
AntigravityManagerProxy se registra en HKCU\Software\Microsoft\Windows\CurrentVersion\Run.
El inicio inmediato usa los servicios locales y no espera una inferencia.

No incluye bases, logs, node_modules, entornos virtuales, perfiles Chrome,
auth.json, auth_c1/c2.json, tokens ni cuentas de Antigravity. Dependencias
de runtime se reconstruyen durante la instalacion. Backups locales no se modifican.
En una reinstalacion un script protegido diferente hace detener la copia antes
de sobrescribir bridge_server.py, consultar_gemini.py o bucle_autonomo.py.

Verificacion sin instalar: instalar.bat -Verificar
