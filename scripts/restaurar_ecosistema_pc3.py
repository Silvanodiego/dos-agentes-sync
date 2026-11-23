"""Restaura componentes adicionales en la PC destino; nunca se ejecuta al empaquetar."""
import json
import os
from pathlib import Path
import shutil
import subprocess


def drive_root(home):
    override = os.environ.get('GOOGLE_DRIVE_ROOT')
    if override:
        return Path(override)
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        for label in ('Mi unidad', 'My Drive'):
            path = Path(letter + ':/') / label
            if path.is_dir():
                return path
    return home / 'Documents/Google Drive'


def app_dir():
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
        '(Get-AppxPackage -Name OpenAI.Codex | Sort-Object Version -Descending | Select-Object -First 1).InstallLocation'],
        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW, check=True)
    if not result.stdout.strip():
        raise RuntimeError('Codex Desktop no instalado. Instalarlo antes de generar su config completo.')
    return Path(result.stdout.strip()) / 'app'


def values(home, root):
    return {'USERPROFILE': str(home), 'DOS_AGENTES_HOME': str(root),
            'LOCALAPPDATA': str(home / 'AppData/Local'), 'DRIVE_ROOT': str(drive_root(home)),
            'CODEX_APP_DIR': str(app_dir())}


def restore(root, home, replacements):
    def rewrite(text):
        # Las plantillas JSON incluyen placeholders; usar / evita escapes invalidos.
        for key, value in replacements.items():
            text = text.replace('%' + key + '%', value.replace('\\', '/'))
        return text

    def copy_tree(source, destination):
        if not source.is_dir():
            return
        for file in source.rglob('*'):
            if not file.is_file():
                continue
            target = destination / file.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            if file.suffix.lower() in {'.py', '.pyw', '.bat', '.cmd', '.json', '.toml', '.yaml', '.yml'}:
                try:
                    text = file.read_text(encoding='utf-8-sig')
                    if any('%' + key + '%' in text for key in replacements):
                        target.write_text(rewrite(text), encoding='utf-8')
                        continue
                except UnicodeError:
                    pass
            shutil.copy2(file, target)

    for directory in ('skills', 'plugins', 'marketplaces', 'rules'):
        copy_tree(root / 'codex' / directory, home / '.codex' / directory)
    for filename in ('RTK.md', 'hooks.json'):
        source = root / 'codex' / filename
        if source.is_file():
            (home / '.codex' / filename).write_text(rewrite(source.read_text(encoding='utf-8-sig')), encoding='utf-8')
    # No reemplazar agy.bat actual por el antiguo adaptador deshabilitado.
    copy_tree(root / 'ScriptsGlobales', home / 'ScriptsGlobales')
    shutil.copy2(root / 'migration_paths.py', home / 'ScriptsGlobales/migration_paths.py')
    for source, target in ((root / 'runtime/.bin', root / '.bin'),
                           (root / 'runtime/agy', home / 'AppData/Local/agy'),
                           (root / 'gemini_config/antigravity-cli', home / '.gemini/antigravity-cli')):
        copy_tree(source, target)
    os.environ['DOS_AGENTES_HOME'] = str(root)
    import winreg
    for key in ('DOS_AGENTES_HOME', 'DOS_AGENTES_ROOT'):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, 'Environment') as environment:
            winreg.SetValueEx(environment, key, 0, winreg.REG_SZ, str(root))
    # Conservar configuraciones MCP de proyectos externos como referencia; no
    # habilitar ejecutables Unity/Brave que no se migraron.
    reference = root / 'gemini_config/config'
    if reference.is_dir():
        copy_tree(reference, home / '.gemini/referencia_migracion')
    for entry in json.loads((root / 'repos_github.json').read_text(encoding='utf-8')):
        if not entry.get('url'):
            continue
        target = root / 'repos_referencia' / entry['name']
        if (target / '.git').exists():
            continue
        # El snapshot contiene cambios portables; importar solo .git del bundle.
        import tempfile
        with tempfile.TemporaryDirectory(prefix='codex-repo-') as tmp:
            subprocess.run(['git', 'clone', '--branch', entry['branch'],
                            str(root / entry['bundle']), tmp], check=True)
            subprocess.run(['git', '-C', tmp, 'remote', 'set-url', 'origin', entry['url']], check=True)
            shutil.copytree(Path(tmp) / '.git', target / '.git')
    print('Skills, plugins, marketplaces, repos Git, modulos Enjambre, agy y herramientas restaurados.', flush=True)
