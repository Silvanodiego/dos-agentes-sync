"""Recupera el alcance completo de v4, sin restaurar su instalador ni datos privados."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tomllib
import zipfile

import tomlkit

MANAGER_NAME = 'Antigravity.Manager-0.30.0-windows-x64-nsis.exe'
MANAGER_SHA = '702ff72d50ff00412bb6b16822131cc5ea6f56e6b28da9edc527c6beb6181762'


def assemble(stage, root, allowed):
    previous = Path.home() / 'Desktop/Migracion_Codex_Limpia_v4.zip'
    if not previous.is_file():
        raise RuntimeError('Se necesita la v4 completa como fuente de recuperacion.')
    prefixes = ('ScriptsGlobales/', 'codex/', 'dependencias/', 'gemini_config/',
                'git_bundles/', 'repos_referencia/', 'runtime/.bin/', 'runtime/agy/')
    standalone = {'repos_github.json', 'repos_github.txt', 'plugins_instalados.json',
                  'migration_paths.py', 'lanzar_node_repl.py'}
    skip = {'ScriptsGlobales/AGENTS.md', 'ScriptsGlobales/agy.bat'}
    recovered = []
    with zipfile.ZipFile(previous) as archive:
        for entry in archive.infolist():
            relative = entry.filename
            path = PurePosixPath(relative)
            if entry.is_dir() or path.is_absolute() or '..' in path.parts:
                continue
            if relative in skip or not allowed(relative):
                continue
            if not (relative.startswith(prefixes) or relative in standalone):
                continue
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(entry))
            recovered.append(relative)
        # La lista completa instalada en PC1; token-saver se instala desde fuente local.
        requirements = archive.read('requirements.txt').decode('utf-8-sig')
        requirements = '\n'.join(line for line in requirements.splitlines()
                                 if line.strip() and not line.strip().lower().startswith('token-saver'))
        requirements += '\npackaging>=23\n'
        (stage / 'requirements.txt').write_text(requirements, encoding='utf-8')
        config = tomllib.loads(archive.read('config.toml').decode('utf-8-sig'))
    # Conservar las fuentes actuales de skills, plugins y repositorios disponibles.
    def overlay(source, destination):
        if not source.is_dir():
            return
        for parent, dirs, files in os.walk(source, followlinks=False):
            relative_parent = Path(parent).relative_to(source)
            dirs[:] = [name for name in dirs if not (Path(parent) / name).is_symlink()
                       and allowed((destination / relative_parent / name / 'probe').as_posix())]
            for name in files:
                file = Path(parent) / name
                relative = destination / relative_parent / name
                if file.is_symlink() or not allowed(relative.as_posix()):
                    continue
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, target)
    overlay(Path.home() / '.codex/skills', Path('codex/skills'))
    overlay(Path.home() / '.codex/plugins', Path('codex/plugins'))
    # Metadatos locales de plugins y scripts auxiliares deben apuntar a la PC
    # destino. No se tocan fuentes protegidas ni los respaldos originales.
    for directory in ('codex', 'ScriptsGlobales', 'gemini_config', 'runtime/.bin'):
        for file in (stage / directory).rglob('*'):
            if not file.is_file() or file.suffix.lower() not in {'.json', '.toml', '.py', '.bat', '.cmd', '.ps1'}:
                continue
            try:
                text = file.read_text(encoding='utf-8-sig')
            except UnicodeError:
                continue
            updated = text.replace(str(Path.home()).replace('\\', '\\\\'), '%USERPROFILE%')
            updated = updated.replace(str(Path.home()), '%USERPROFILE%')
            updated = updated.replace(str(Path.home()).replace('\\', '/'), '%USERPROFILE%')
            updated = updated.replace('I:\\\\Mi unidad', '%DRIVE_ROOT%').replace('I:\\Mi unidad', '%DRIVE_ROOT%')
            updated = updated.replace('I:/Mi unidad', '%DRIVE_ROOT%')
            updated = updated.replace('%DOS_AGENTES_HOME%/scripts/DOS_AGENTES', '%DOS_AGENTES_HOME%')
            if updated != text:
                file.write_text(updated, encoding='utf-8')
    # Los snapshots de v4 ya tienen sus rutas portables; regenerar sus bundles
    # cuando el repositorio local tiene una revision mas nueva.
    repositories = json.loads((stage / 'repos_github.json').read_text(encoding='utf-8-sig'))
    for repo in repositories:
        repo.pop('path', None)
        local = root / 'repos_referencia' / repo['name']
        if not repo.get('url'):
            continue
        if (local / '.git').exists():
            current = subprocess.check_output(['git', '-C', str(local), 'rev-parse', 'HEAD'], text=True).strip()
            if current != repo['commit']:
                raise RuntimeError('Cambio de revision no revisado en repositorio: ' + repo['name'])
        if not (stage / repo['bundle']).is_file():
            raise RuntimeError('Falta bundle Git: ' + repo['name'])
        subprocess.run(['git', 'bundle', 'verify', str(stage / repo['bundle'])], cwd=root, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (stage / 'repos_github.json').write_text(json.dumps(repositories, indent=2), encoding='utf-8')
    # Nuevo repo principal incluido tambien como bundle: el primer clon no requiere login.
    subprocess.run(['git', 'bundle', 'create', str(stage / 'git_bundles/dos-agentes-sync.bundle'),
                    'main'], cwd=root, check=True)
    shared = tomllib.loads((stage / 'config_compartida/config.toml').read_text(encoding='utf-8-sig'))
    config.setdefault('mcp_servers', {})['antigravity_bridge'] = shared['mcp_servers']['antigravity_bridge']
    config['projects'] = {'%DOS_AGENTES_HOME%': {'trust_level': 'trusted'}}
    config['sandbox_workspace_write']['writable_roots'] = [
        '%DOS_AGENTES_HOME%', '%USERPROFILE%/ScriptsGlobales', '%USERPROFILE%/.codex']
    # El launcher descubre app/pipe en la PC nueva; no congelar el build de PC1.
    config['mcp_servers']['node_repl']['env'].pop('BROWSER_USE_CODEX_APP_VERSION', None)
    rendered = tomlkit.dumps(config)
    tomllib.loads(rendered)
    if 'C:\\Users\\H_P' in rendered or 'I:\\' in rendered:
        raise RuntimeError('La plantilla completa contiene rutas fijas.')
    (stage / 'config.toml').write_text(rendered, encoding='utf-8')
    # Raiz portable comun para los modulos recuperados.
    helper = stage / 'migration_paths.py'
    text = helper.read_text(encoding='utf-8-sig')
    text = text.replace("str(pathlib.Path(os.environ['LOCALAPPDATA'])/'dos_agentes_local')",
                        'str(pathlib.Path(__file__).resolve().parent)')
    helper.write_text(text, encoding='utf-8')
    # Manager completo como instalador oficial: evita copiar node_modules sueltos
    # y conserva sus dependencias internas firmadas por el distribuidor.
    manager = Path(os.environ['TEMP']) / MANAGER_NAME
    if not manager.is_file() or hashlib.file_digest(manager.open('rb'), 'sha256').hexdigest() != MANAGER_SHA:
        raise RuntimeError('Falta instalador oficial verificado de Antigravity Manager 0.30.0.')
    destination = stage / 'runtime/installers' / MANAGER_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manager, destination)
    node_name = 'node-v24.22.3-win-x64.zip'
    node = Path(os.environ['TEMP']) / node_name
    node_sha = 'e612af99f626ab415ea225af6bce5c971feb448cb5cae250bb1c3fa50c5f7d9f'
    if not node.is_file() or hashlib.sha256(node.read_bytes()).hexdigest() != node_sha:
        raise RuntimeError('Falta ZIP oficial Node24 verificado en TEMP: ' + node_name)
    shutil.copy2(node, stage / 'runtime/installers' / node_name)
    settings = Path.home() / '.antigravity-agent/gui_config.json'
    safe = {}
    if settings.is_file():
        current = json.loads(settings.read_text(encoding='utf-8-sig'))
        # Solo preferencias de interfaz y arranque; ninguna cuenta o token.
        safe = {key: current[key] for key in ('theme', 'language', 'auto_start', 'minimize_to_tray') if key in current}
    (stage / 'antigravity_config').mkdir(exist_ok=True)
    (stage / 'antigravity_config/gui_config.json').write_text(json.dumps(safe, indent=2), encoding='utf-8')
    required = ['runtime/agy', 'runtime/.bin', 'codex/skills', 'codex/plugins',
                'codex/marketplaces', 'ScriptsGlobales/modulos_enjambre',
                'ScriptsGlobales/puente_gemini', 'repos_referencia/AntigravityManager',
                'repos_referencia/token-saver', 'repos_referencia/agent-orchestrator']
    for group in required:
        if not any(p.is_file() for p in (stage / group).rglob('*')):
            raise RuntimeError('Grupo incompleto: ' + group)
    inventory = []
    for group in required + ['git_bundles', 'runtime/installers', 'gemini_config', 'dependencias']:
        files = [p for p in (stage / group).rglob('*') if p.is_file()]
        inventory.append({'component': group, 'files': len(files), 'bytes': sum(p.stat().st_size for p in files)})
    (stage / 'INVENTARIO_ECOSISTEMA.json').write_text(json.dumps({
        'version': 'v8', 'components': inventory, 'recovered_from_v4': len(recovered),
        'manager': {'version': '0.30.0', 'sha256': MANAGER_SHA},
        'exclusions': 'DB, logs, caches, node_modules, venv, auth.json, perfiles Chrome y credenciales Antigravity',
        'external_projects': 'No se migran proyectos externos Unity/Patitas/MISC ni sus MCP especificos.'
    }, indent=2), encoding='utf-8')
    (stage / 'LEEME_ECOSISTEMA.txt').write_text(
        'V8 COMPLETA: fuentes actuales + ecosistema recuperado de v4.\n'
        'Inventario exacto y hashes: MANIFIESTO_SHA256.json; resumen: INVENTARIO_ECOSISTEMA.json.\n'
        'Manager 0.30.0 incluye sus dependencias en el instalador oficial NSIS.\n'
        'No incluye entornos ni node_modules sueltos: el instalador los reconstruye con pip/npm.\n'
        'Internet y autorizacion UAC son necesarios para requisitos del sistema.\n'
        'Autenticar de nuevo Antigravity/Gemini/GitHub y conectores OAuth.\n'
        'Los MCP de proyectos Unity/Patitas/MISC quedan como referencia, no se activan sin esos proyectos.\n', encoding='utf-8')
