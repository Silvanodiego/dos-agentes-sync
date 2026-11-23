"""Sincronizacion acotada, sin prompts, con estado y credenciales solo locales."""
import contextlib
import datetime
import hashlib
import importlib.metadata
import json
import logging
import msvcrt
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / '.sync-local'
LOCAL.mkdir(exist_ok=True)
logging.basicConfig(filename=LOCAL / 'sync.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
ENV = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never',
           GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=10')
FLAGS = subprocess.CREATE_NO_WINDOW


def run(args, timeout=45, env=None):
    try:
        result = subprocess.run([str(a) for a in args], cwd=ROOT, env=env or ENV,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding='utf-8', errors='replace',
                                creationflags=FLAGS, timeout=timeout)
        # No se vuelca stdout: remotos privados y herramientas pueden revelar datos.
        return result.returncode, result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        logging.warning('Comando %s: %s', Path(str(args[0])).name, type(exc).__name__)
        return 124, ''


def git_exe():
    candidates = [shutil.which('git.exe'),
                  str(Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git/cmd/git.exe'),
                  str(Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')]
    # El PATH de las tareas puede no incluir el runtime del escritorio.
    candidates += [str(p) for p in Path('C:/Program Files/WindowsApps').glob(
        'OpenAI.CodexPrimaryRuntime*/dependencies/native/git/cmd/git.exe')]
    return next((p for p in candidates if p and Path(p).is_file()), None)


def git_sync(mode):
    binary = git_exe()
    if not binary:
        logging.warning('Git no encontrado; continua la copia local')
        return 'git-no-disponible'
    def git(*args):
        return run([binary, '-c', 'http.connectTimeout=10', '-c', 'http.lowSpeedLimit=1',
                    '-c', 'http.lowSpeedTime=15', *args])
    if git('diff', '--name-only', '--diff-filter=U')[1] or any(
        (ROOT / '.git' / name).exists() for name in ('rebase-merge', 'rebase-apply', 'MERGE_HEAD')):
        logging.error('Conflicto/operacion Git pendiente: no se modifican archivos ni reglas')
        return 'conflicto'
    remote = git('remote', 'get-url', 'origin')[0] == 0
    if mode == 'periodic':
        if git('add', '--all')[0]:
            return 'error-add'
        staged = git('diff', '--cached', '--quiet')[0]
        if staged == 1:
            scanner = ROOT / '.bin/gitleaks.exe'
            if scanner.exists() and run([scanner, 'git', '--staged', '--redact', '--no-banner', ROOT])[0]:
                logging.error('Revision de secretos rechazo el commit; revisar localmente')
                return 'revision-secretos'
            message = 'Sync automatico ' + socket.gethostname() + ' ' + datetime.datetime.now().isoformat(timespec='seconds')
            if git('commit', '-m', message)[0]:
                logging.error('Commit fallo: comprobar identidad Git local')
                return 'error-commit'
        elif staged != 0:
            return 'error-diff'
    if not remote:
        logging.info('Sin origin: commit/copia local conservados; pendiente conectar GitHub')
        return 'sin-remoto'
    branch = git('branch', '--show-current')[1]
    if not branch:
        return 'sin-rama'
    args = ['pull', '--ff-only'] if mode == 'startup' else ['pull', '--rebase', '--autostash']
    code, _ = git(*args, 'origin', branch)
    if code:
        logging.warning('Pull fallo; se conserva copia local. No se fuerza ni descarta contenido.')
        if git('diff', '--name-only', '--diff-filter=U')[1] or (ROOT / '.git/rebase-merge').exists():
            return 'conflicto'
        return 'pull-pendiente'
    if mode == 'periodic' and git('push', '--set-upstream', 'origin', branch)[0]:
        logging.warning('Push pendiente; se reintentara en la proxima ejecucion')
        return 'push-pendiente'
    logging.info('Git sincronizado (%s)', mode)
    return 'ok'


def apply_shared():
    targets = [('AGENTS.md', Path.home() / '.codex/AGENTS.md'),
               ('AGENTS.md', ROOT / 'AGENTS.md'),
               ('agy.bat', Path.home() / 'ScriptsGlobales/agy.bat')]
    for name, target in targets:
        source = ROOT / 'config_compartida' / name
        data = source.read_bytes()
        if target.exists() and target.read_bytes() == data:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            stamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
            shutil.copy2(target, LOCAL / ('backup-' + stamp + '-' + target.name))
        temporary = target.with_suffix(target.suffix + '.sync.tmp')
        temporary.write_bytes(data)
        os.replace(temporary, target)
        logging.info('Actualizado %s', name)


def dependencies():
    state_path = LOCAL / 'dependencies.json'
    try:
        state = json.loads(state_path.read_text())
    except (OSError, ValueError):
        state = {}
    for name in ('requirements.txt', 'package.json'):
        manifest = ROOT / name
        if not manifest.exists():
            continue
        digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
        if state.get(name) == digest:
            continue
        success = True
        if name == 'requirements.txt':
            # Mantiene versiones instaladas: solo instala distribuciones ausentes.
            try:
                from packaging.requirements import Requirement
            except ImportError:
                code, _ = run([sys.executable, '-m', 'pip', 'install', '--no-input',
                               '--retries', '0', '--timeout', '12', 'packaging'], timeout=60)
                if code:
                    logging.warning('Falta packaging; dependencias pendientes')
                    continue
                from packaging.requirements import Requirement
            constraints = LOCAL / 'installed-constraints.txt'
            constraints.write_text('\n'.join(f'{d.metadata["Name"]}=={d.version}'
                                           for d in importlib.metadata.distributions()
                                           if d.metadata.get('Name')), encoding='utf-8')
            for line in manifest.read_text(encoding='utf-8-sig').splitlines():
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                req = Requirement(line)
                if req.marker and not req.marker.evaluate():
                    continue
                try:
                    importlib.metadata.version(req.name)
                except importlib.metadata.PackageNotFoundError:
                    code, _ = run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                                   '--no-input', '--retries', '0', '--timeout', '12',
                                   '-c', constraints, line], timeout=90)
                    success = success and code == 0
        else:
            package = json.loads(manifest.read_text(encoding='utf-8-sig'))
            wanted = dict(package.get('dependencies', {}), **package.get('devDependencies', {}))
            missing = [f'{n}@{v}' for n, v in wanted.items()
                       if not (ROOT / 'node_modules' / n / 'package.json').exists()]
            if missing:
                npm = shutil.which('npm.cmd')
                if not npm:
                    success = False
                else:
                    # Instala en staging y copia solo paquetes ausentes: no actualiza existentes.
                    stage = LOCAL / 'npm-stage'
                    stage.mkdir(exist_ok=True)
                    code, _ = run([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', npm,
                                   'install', '--prefix', stage, '--no-save', '--package-lock=false',
                                   '--no-audit', '--no-fund', '--fetch-retries=0',
                                   '--fetch-timeout=15000', *missing], timeout=120)
                    success = code == 0
                    if success:
                        for source in (stage / 'node_modules').iterdir():
                            destination = ROOT / 'node_modules' / source.name
                            if source.name.startswith('@') or source.name == '.bin':
                                destination.mkdir(parents=True, exist_ok=True)
                                for child in source.iterdir():
                                    if not (destination / child.name).exists():
                                        if child.is_dir():
                                            shutil.copytree(child, destination / child.name)
                                        else:
                                            shutil.copy2(child, destination / child.name)
                            elif not destination.exists():
                                shutil.copytree(source, destination)
        if success:
            state[name] = digest
            logging.info('Dependencias revisadas: %s; paquetes existentes conservados', name)
        else:
            logging.warning('Dependencias pendientes: %s; reintento siguiente ejecucion', name)
    state_path.write_text(json.dumps(state), encoding='utf-8')


def listening(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.4):
            return True
    except OSError:
        return False


def start_services():
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    failures = []
    for script, port in [('bridge_server.py', 8765), ('panel_web_ag/server.py', 8787)]:
        if not listening(port):
            subprocess.Popen([str(pythonw), '-X', 'utf8', str(ROOT / script)], cwd=ROOT,
                             creationflags=FLAGS, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(20):
                if listening(port):
                    break
                time.sleep(0.2)
        if not listening(port):
            failures.append(script)
    # PowerShell obtiene comandos completos sin dependencia de psutil.
    code, output = run(['powershell.exe', '-NoProfile', '-Command',
        "@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'pythonw.exe' -and $_.CommandLine -like '*monitor_cuota.pyw*' }).Count"])
    if code:
        failures.append('comprobacion-monitor')
    elif output == '0':
        process = subprocess.Popen([str(pythonw), str(ROOT / 'monitor_cuota.pyw')], cwd=ROOT,
                                   creationflags=FLAGS, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        if process.poll() is not None:
            failures.append('monitor_cuota.pyw')
    if failures:
        raise RuntimeError('Servicios no iniciados: ' + ', '.join(failures))
    logging.info('Servicios disponibles: puente 8765, panel 8787, monitor')


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'periodic'
    if mode not in ('startup', 'periodic'):
        return 2
    with open(LOCAL / 'sync.lock', 'a+b') as lock:
        lock.seek(0)
        lock.write(b'0')
        lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            logging.info('Otra sincronizacion esta en curso')
            return 0
        status = git_sync(mode)
        if status == 'conflicto':
            if mode == 'startup':
                start_services()
            return 1
        apply_shared()
        try:
            dependencies()
        except Exception as exc:
            logging.warning('Dependencias pendientes: %s', type(exc).__name__)
        if mode == 'startup':
            start_services()
        (LOCAL / 'last-run.json').write_text(json.dumps({
            'mode': mode, 'git': status, 'time': datetime.datetime.now().isoformat()}))
        return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        logging.exception('Sincronizacion interrumpida')
        sys.exit(1)
