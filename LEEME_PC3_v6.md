# Migracion Codex Limpia v6

Extraer la carpeta completa en una ruta local y ejecutar instalar.bat.
El instalador muestra seis etapas en vivo, valida SHA256 antes de instalar,
solicita Administrador, instala requisitos faltantes y prepara C:\dos_agentes_local.
Necesita Internet y winget (App Installer de Microsoft). Incluye bundles Git
del repositorio principal main y cinco repositorios de referencia para el primer clon.
Para sincronizar despues con https://github.com/Silvanodiego/dos-agentes-sync.git,
si el repositorio requiere autenticacion, iniciar sesion con Git Credential Manager.
No se transfieren credenciales de GitHub en el paquete.

Python 3.11-3.14, Git y Node.js LTS 24; pip instala los tres requirements.
npm ci respeta package-lock.json. Ante un fallo instala VCTools/Windows SDK
y reintenta una vez. Los errores finales son visibles y no se anuncian como exito.
Token-saver se instala desde repos_referencia/token-saver, sin buscarlo en PyPI.
Instala tambien los globales npm de PC1: Codex CLI, context-mode, ctx7 y opencode-ai.
Verifica better-sqlite3 abriendo una base en memoria. Codex Desktop se instala
desde Microsoft Store si falta; se detecta su runtime antes de generar el TOML.

Antigravity Manager: instalador oficial NSIS 0.30.0 x64 incluido, misma version
que PC1, con SHA256 contrastado contra la release oficial de Draculabo.
No depende de una descarga durante la instalacion. Se instala en AntigravityManager.
La PC 3 obtiene claves locales nuevas; hay que volver a autenticar las cuentas
en Antigravity Manager y Gemini (las credenciales DPAPI no son portables).
Incluye las exportaciones Codex auth_c1.json y auth_c2.json solicitadas para
el monitor. Si no existe auth.json en el usuario destino, se crea desde auth_c1.
Si la sesion Codex expiro, volver a autenticar esa cuenta.

La plantilla TOML contiene %USERPROFILE%: el instalador expande los valores
parseados y escribe rutas reales del usuario nuevo, porque TOML no expande
variables de entorno. Conserva un notify ya existente sin duplicarlo, valida
con tomllib y habilita el MCP antigravity_bridge. Rechaza TOML previo invalido.

Cascada AG: bridge_server.py (8765) -> Antigravity Manager (8045).
Chat Fijo Gemini: chat_fijo_gemini.py + piloto_gemini.py -> Chrome/Edge CDP 9222,
separado de Cascada AG. Abrir abrir_chrome_gemini.bat para autenticar Gemini.
Se crean bases vacias a partir del esquema, sin historial ni URL de chats privados.
El panel escucha en 8787. ScriptsGlobales recibe agy.bat y antigravity_mcp.bat.
Ademas se restauran skills, plugins, marketplaces, modulos_enjambre,
puente_gemini, CLI agy y herramientas binarias. INVENTARIO_ECOSISTEMA.json
resume los grupos; MANIFIESTO_SHA256.json enumera todos los archivos y hashes.
Los MCP de proyectos externos no incluidos se conservan como referencia;
Patitas, MISC y Unity no se copian ni se activan sin sus proyectos originales.

Inicio: DosAgentesInicioOculto.lnk ejecuta arrancar_todo_oculto.vbs mediante
wscript; tarea DosAgentesGitSync (auto_sync_git) cada diez minutos, oculta,
ejecuta scripts/sync_silencioso.vbs periodic, el mismo flujo de auto_sync_git.bat.
AntigravityManagerProxy se registra en HKCU\Software\Microsoft\Windows\CurrentVersion\Run.
El inicio inmediato usa los servicios locales y no espera una inferencia.

No incluye bases, logs, node_modules, entornos virtuales, perfiles Chrome,
auth.json ni tokens o cuentas de Antigravity. Las dos exportaciones Codex
auth_c1/c2.json quedan fuera de Git. Dependencias
de runtime se reconstruyen durante la instalacion. Backups locales no se modifican.
En una reinstalacion un script protegido diferente hace detener la copia antes
de sobrescribir bridge_server.py, consultar_gemini.py o bucle_autonomo.py.

Verificacion sin instalar: instalar.bat -Verificar

Correccion v6: winget/Git/pip/npm reciben argumentos separados en PowerShell 5.1.
La prueba scripts/test_argumentos_instalador_pc3.ps1 no instala paquetes.
