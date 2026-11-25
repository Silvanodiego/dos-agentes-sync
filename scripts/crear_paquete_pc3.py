"""Construye v8 desde las fuentes Git, con exclusion estricta e integridad."""
import argparse
import ast
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parent.parent
NAME = 'Migracion_Codex_Limpia_v8'
PROTECTED = ('bridge_server.py', 'consultar_gemini.py', 'bucle_autonomo.py')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def allowed(relative):
    path = PurePosixPath(relative)
    parts = [s.lower() for s in path.parts]
    forbidden_dirs = {'logs', 'node_modules', '__pycache__', '.venv', 'venv', '.git',
                      'chrome_gemini_profile', '.antigravity-agent', '.sync-local',
                      'config_backups', 'sessions', '.cache', 'tmp', 'temp', 'cookies',
                      'credentials', 'credenciales', '.plugin-appserver'}
    if forbidden_dirs.intersection(parts):
        return False
    if path.as_posix().lower() == 'runtime/installers/node-v24.22.3-win-x64.zip':
        return True  # Distribucion oficial verificada, necesaria para instalar npm/npx.
    name = parts[-1]
    # Exportaciones Codex solicitadas para migrar; nunca se agregan a Git.
    if len(parts) == 1 and name in ('auth_c1.json', 'auth_c2.json'):
        return True
    patterns = ('*.db', '*.db-*', '*.sqlite*', '*.log', '*.jsonl', '*.pyc', '*.bak',
                '*_bak_*', '*_backup*', 'auth*.json', '*credentials*', '*token*.json',
                'local_bridge_token', '.env', '.env.*', '*.pem', '*.key', '*.zip', '*.tmp', '*.old')
    return not any(fnmatch.fnmatch(name, p) for p in patterns)


def build(desktop: Path, drive: Path):
    protected = {name: sha(ROOT / name) for name in PROTECTED}
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    sources = sorted(set(p for p in paths if p and allowed(p)))
    for name in ('auth_c1.json', 'auth_c2.json'):
        if not (ROOT / name).is_file():
            raise RuntimeError('Falta la exportacion solicitada: ' + name)
        sources.append(name)
    if any(not (ROOT / p).is_file() for p in sources):
        raise RuntimeError('Hay fuentes Git faltantes.')
    with tempfile.TemporaryDirectory(prefix='codex-v8-package-') as tmp:
        stage = Path(tmp) / NAME
        stage.mkdir()
        for relative in sources:
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        shutil.copy2(stage / 'config_compartida/AGENTS.md', stage / 'AGENTS.md')
        shutil.copy2(stage / 'config_compartida/agy.bat', stage / 'agy.bat')
        from ecosistema_paquete_pc3 import assemble
        print('Recuperando ecosistema completo y verificando bundles...', flush=True)
        assemble(stage, ROOT, allowed)
        required = ('instalar.bat', 'scripts/instalar_pc3.ps1', 'scripts/configurar_pc3.py',
                    'scripts/esquemas_pc3.py', 'scripts/node_pc3.ps1',
                    'scripts/copiar_paquete_pc.ps1', 'scripts/validar_scripts_protegidos.py',
                    'scripts/test_copiar_paquete_pc.ps1', 'scripts/github_pc.ps1',
                    'scripts/verificar_npm_instalado.py', 'activar_chats_esta_pc.bat',
                    'scripts/chats/registrar_activacion_automatica.ps1',
                    'scripts/chats/activar_cuando_listo.py', 'scripts/chats/sync_chats_abierto.py',
                    'scripts/chats/proyectos_portables.py', 'scripts/chats/continuidad_chats.py',
                    'scripts/chats/rutas_historial.py',
                    'runtime/installers/node-v24.22.3-win-x64.zip', 'arrancar_todo_oculto.vbs',
                    'chat_fijo_gemini.py', 'piloto_gemini.py', 'abrir_chrome_gemini.bat',
                    'abrir_chrome_gemini_oculto.bat', 'AGENTS.md', 'agy.bat',
                    'antigravity_mcp.mjs', 'panel_web_ag/server.py', 'monitor_cuota.pyw')
        for relative in required:
            if not (stage / relative).is_file():
                raise RuntimeError('Falta componente: ' + relative)
        tomllib.loads((stage / 'config_compartida/config.toml').read_text(encoding='utf-8-sig'))
        for relative in sources:
            if relative.endswith(('.py', '.pyw')):
                ast.parse((stage / relative).read_text(encoding='utf-8-sig'), filename=relative)
        rows = [{'path': p.relative_to(stage).as_posix(), 'sha256': sha(p), 'bytes': p.stat().st_size}
                for p in sorted(stage.rglob('*')) if p.is_file()]
        manifest = {'version': 'v8', 'git_commit': subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'protected_sha256': protected, 'files': rows}
        (stage / 'MANIFIESTO_SHA256.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        result = subprocess.run(['cmd.exe', '/d', '/c', str(stage / 'instalar.bat'), '-Verificar'],
                                cwd=stage, check=False)
        if result.returncode:
            raise RuntimeError('Fallo instalar.bat -Verificar.')
        subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                        '-File', str(stage / 'scripts/test_argumentos_instalador_pc3.ps1')],
                       cwd=stage, check=True)
        subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                        '-File', str(stage / 'scripts/test_node_pc3.ps1'),
                        '-Archive', str(stage / 'runtime/installers/node-v24.22.3-win-x64.zip')],
                       cwd=stage, check=True)
        subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                        '-File', str(stage / 'scripts/test_copiar_paquete_pc.ps1')],
                       cwd=stage, check=True)
        subprocess.run([str(ROOT / '.venv/Scripts/python.exe'),
                        str(stage / 'scripts/test_v8_reinstalacion.py')], cwd=stage, check=True)
        subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                        '-File', str(stage / 'scripts/test_github_pc.ps1')], cwd=stage, check=True)
        zip_path = Path(tmp) / (NAME + '.zip')
        with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6,
                             strict_timestamps=False) as archive:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    archive.write(path, NAME + '/' + path.relative_to(stage).as_posix())
        with zipfile.ZipFile(zip_path) as archive:
            assert archive.testzip() is None
            actual = {n.removeprefix(NAME + '/') for n in archive.namelist()}
            assert actual == {row['path'] for row in rows} | {'MANIFIESTO_SHA256.json'}
            for row in rows:
                assert allowed(row['path']), row['path']
                assert hashlib.sha256(archive.read(NAME + '/' + row['path'])).hexdigest() == row['sha256']
            for name, digest in protected.items():
                assert hashlib.sha256(archive.read(NAME + '/' + name)).hexdigest() == digest
        assert protected == {name: sha(ROOT / name) for name in PROTECTED}
        for destination in (desktop, drive):
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(zip_path, destination)
        assert sha(desktop) == sha(drive) == sha(zip_path)
        print(json.dumps({'desktop': str(desktop), 'drive': str(drive), 'bytes': desktop.stat().st_size,
                          'sha256': sha(desktop), 'files': len(rows) + 1,
                          'protected_sha256': protected}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--desktop', type=Path, default=Path.home() / 'Desktop' / (NAME + '.zip'))
    parser.add_argument('--drive', type=Path, default=Path('I:/Mi unidad') / (NAME + '.zip'))
    args = parser.parse_args()
    build(args.desktop, args.drive)
