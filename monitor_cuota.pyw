import json
import logging
import os
import pathlib
import subprocess
import threading
import time
import pystray
from PIL import Image, ImageDraw, ImageFont
import urllib.request

BASE = pathlib.Path(__file__).resolve().parent
LIVE_AUTH = pathlib.Path.home() / '.codex' / 'auth.json'
AUTHS = {1: BASE / 'auth_c1.json', 2: BASE / 'auth_c2.json'}
SESSIONS = {1: pathlib.Path.home() / '.codex' / 'sessions',
            2: pathlib.Path.home() / '.cx' / 'ejecutor' / 'sessions'}
KEEP_CHATS = 2
IDLE_SECONDS = 15
QUOTA_INTERVAL = 30
MAX_QUOTA_AGE = 90
AUTH_LOCK = threading.RLock()
ROTATION_STATE = BASE / '.sync-local' / 'rotacion_cuota.json'
logging.basicConfig(filename=BASE / 'monitor_cuota.log', level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')


def auth_data(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def account_id(path):
    return (auth_data(path).get('tokens') or {}).get('account_id')


def active_account():
    try:
        current = account_id(LIVE_AUTH)
        matches = [n for n, path in AUTHS.items() if current and account_id(path) == current]
        return matches[0] if len(matches) == 1 else None
    except (OSError, ValueError):
        return None


def session_files(directory):
    found = []
    for path in directory.rglob('*.jsonl'):
        try:
            found.append((path.stat().st_mtime, path))
        except OSError:
            pass
    return sorted(found, key=lambda item: item[0], reverse=True)


def latest_write():
    # Desktop always writes in .codex, including after switching to account 2.
    files = session_files(SESSIONS[1])
    writes = [files[0][0]] if files else []
    # Codex actual tambien persiste chats en SQLite/WAL, sin tocar el rollout.
    for pattern in ('state_*.sqlite', 'state_*.sqlite-wal',
                    'thread_history_*.sqlite', 'thread_history_*.sqlite-wal'):
        for path in SESSIONS[1].parent.glob(pattern):
            try:
                writes.append(path.stat().st_mtime)
            except OSError:
                pass
    return max(writes) if writes else None


def cleanup_old_chats():
    # Los historiales existentes tambien se sincronizan: nunca eliminarlos aqui.
    return


def rotation_blocked():
    try:
        return bool(json.loads(ROTATION_STATE.read_text(encoding='utf-8-sig'))['blocked'])
    except FileNotFoundError:
        return False
    except (OSError, ValueError, KeyError):
        # Un estado ilegible nunca habilita cierres automaticos de Codex.
        return True


def block_rotation(reason):
    ROTATION_STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = ROTATION_STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps({'blocked': True, 'reason': reason,
                                     'time': time.time()}), encoding='utf-8')
    os.replace(temporary, ROTATION_STATE)


def fetch_quota(number):
    # Preserve refreshed credentials of the currently active account.
    with AUTH_LOCK:
        if active_account() == number:
            atomic_copy(LIVE_AUTH, AUTHS[number])
        tokens = auth_data(AUTHS[number])['tokens']
    request = urllib.request.Request(
        'https://chatgpt.com/backend-api/wham/usage',
        headers={'Authorization': 'Bearer ' + tokens['access_token'],
                 'ChatGPT-Account-Id': tokens['account_id'],
                 'User-Agent': 'CodexQuotaMonitor/1.0'})
    with urllib.request.urlopen(request, timeout=12) as response:
        limits = json.load(response)['rate_limit']
    values = []
    for window in ('primary_window', 'secondary_window'):
        used = (limits.get(window) or {}).get('used_percent')
        values.append(max(0.0, min(100.0, 100 - float(used))) if used is not None else None)
    return (*values, time.time())


def atomic_copy(source, target):
    content = source.read_bytes()
    json.loads(content.decode('utf-8-sig'))
    temporary = target.with_name(target.name + '.monitor.tmp')
    try:
        temporary.write_bytes(content)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def should_switch(active, quotas, last_write, now):
    if active not in (1, 2) or last_write is None or now - last_write < IDLE_SECONDS:
        return False
    own, other = quotas.get(active), quotas.get(3 - active)
    if not own or not other or any(now - q[2] > MAX_QUOTA_AGE for q in (own, other)):
        return False
    return (any(v is not None and v <= 5 for v in own[:2])
            and all(v is not None and v > 10 for v in other[:2]))


DESKTOP = None


def desktop_target():
    global DESKTOP
    if DESKTOP is None:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
             "$p=Get-AppxPackage -Name OpenAI.Codex | Select-Object -First 1; "
             "if (!$p) { exit 1 }; $p.InstallLocation; $p.PackageFamilyName + '!App'"],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode or len(result.stdout.strip().splitlines()) != 2:
            raise RuntimeError('Codex Desktop no esta instalado')
        DESKTOP = tuple(result.stdout.strip().splitlines())
    return DESKTOP


def switch_account(expected, destination, reason='manual'):
    started = time.monotonic()
    install, app_id = desktop_target()
    with AUTH_LOCK:
        if active_account() != expected:
            raise RuntimeError('La cuenta activa cambio antes del cierre')
        if not account_id(AUTHS[destination]) or account_id(AUTHS[destination]) == account_id(LIVE_AUTH):
            raise RuntimeError('Cuenta destino invalida o duplicada')
        atomic_copy(LIVE_AUTH, AUTHS[expected])
        logging.info('ROTACION inicio motivo=%s C%s -> C%s', reason, expected, destination)
        # Kill only the installed Codex app and its descendants; do not kill other ChatGPT apps.
        script = r"""
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($env:CODEX_MONITOR_INSTALL).TrimEnd('\') + '\'
$targets = @(Get-Process | Where-Object {
    $_.Path -and $_.Path.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) -and
    $_.ProcessName -in @('ChatGPT','Codex','codex','codex-code-mode-host')
})
$ErrorActionPreference = 'Continue'  # A parent kill may already have removed its children.
foreach ($p in $targets) {
    & taskkill.exe /PID $p.Id /T /F 2>$null | Out-Null
}
$ErrorActionPreference = 'Stop'
$remaining = @(Get-Process | Where-Object {
    $_.Path -and $_.Path.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) -and
    $_.ProcessName -in @('ChatGPT','Codex','codex','codex-code-mode-host')
})
if ($remaining.Count) { throw 'Quedaron procesos de Codex abiertos' }
"""
        env = dict(os.environ, CODEX_MONITOR_INSTALL=install)
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                                env=env, capture_output=True, text=True, timeout=20,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        logging.info('ROTACION cierre procesos resultado=%s duracion=%.2fs', result.returncode,
                     time.monotonic() - started)
        if result.returncode:
            # El cierre fallo antes de tocar auth.json. No copiar ni relanzar.
            # Registrar solo el codigo; stderr podria contener datos del entorno.
            raise RuntimeError('No se pudieron cerrar todos los procesos de Codex; '
                               'rotacion automatica pausada')
        try:
            if active_account() != expected:
                raise RuntimeError('La cuenta activa cambio durante el cierre')
            atomic_copy(LIVE_AUTH, AUTHS[expected])
            atomic_copy(AUTHS[destination], LIVE_AUTH)
            if active_account() != destination:
                raise RuntimeError('No se pudo verificar auth.json de destino')
            logging.info('ROTACION auth.json verificado cuenta=C%s', destination)
        except Exception:
            atomic_copy(AUTHS[expected], LIVE_AUTH)
            logging.exception('ROTACION fallo; cuenta C%s restaurada', expected)
            raise
        finally:
            subprocess.Popen(['explorer.exe', 'shell:AppsFolder\\' + app_id], close_fds=True)
            logging.info('ROTACION relanzamiento solicitado')
        verify_desktop_started(install)
        logging.info('ROTACION OK motivo=%s C%s -> C%s total=%.2fs', reason, expected,
                     destination, time.monotonic() - started)


def verify_desktop_started(install):
    script = r"""
$root = [IO.Path]::GetFullPath($env:CODEX_MONITOR_INSTALL).TrimEnd('\') + '\'
$deadline = [DateTime]::UtcNow.AddSeconds(10)
do {
    $app = Get-Process -Name ChatGPT,Codex -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -and $_.Path.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)
    } | Select-Object -First 1
    if ($app) { Write-Output $app.Id; exit 0 }
    Start-Sleep -Milliseconds 200
} while ([DateTime]::UtcNow -lt $deadline)
exit 1
"""
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            env=dict(os.environ, CODEX_MONITOR_INSTALL=install),
                            capture_output=True, text=True, timeout=15,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError('Auth actualizado, pero no se pudo confirmar el reinicio de Codex')
    logging.info('ROTACION Codex Desktop iniciado confirmado')


def color_for(value):
    return '#aaaaaa' if value is None else '#4ade80' if value > 40 else '#facc15' if value > 15 else '#f87171'


def tray_image(value):
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 63, 63), radius=12, fill='#18181b')
    text = '--' if value is None else str(min(99, max(0, round(value))))
    size = 50 if len(text) <= 2 else 34
    for font_name in ('arialbd.ttf', 'segoeuib.ttf'):
        font_path = str(pathlib.Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts' / font_name)
        try:
            font = ImageFont.truetype(font_path, size)
            break
        except OSError:
            continue
    else:
        font = ImageFont.load_default(size=size)
    box = draw.textbbox((0, 0), text, font=font)
    width, height = box[2] - box[0], box[3] - box[1]
    draw.text(((64 - width) / 2 - box[0], (64 - height) / 2 - box[1]),
              text, font=font, fill=color_for(value))
    return image


def tray_summary(active, quotas, now):
    lines = []
    active_value = None
    for number in (1, 2):
        quota = quotas.get(number)
        values = quota[:2] if quota and now - quota[2] <= MAX_QUOTA_AGE else (None, None)
        display = [f'{v:g}%' if v is not None else '--%' for v in values]
        lines.append(f"C{number}{' (ACTIVA)' if number == active else ''}: 5h {display[0]} | Sem {display[1]}")
        if number == active:
            active_value = values[0]
    if active is None:
        lines.append('Cuenta activa desconocida')
    return '\n'.join(lines), active_value


def trigger_new_chat():
    script = r"""
$pkg = Get-AppxPackage -Name OpenAI.Codex | Select-Object -First 1
if (-not $pkg) { exit 1 }
$exe = Join-Path $pkg.InstallLocation 'app\ChatGPT.exe'
$app = Get-Process | Where-Object { $_.Path -eq $exe -and $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if ($app) {
    $ws = New-Object -ComObject WScript.Shell
    if ($ws.AppActivate([int]$app.Id)) {
        Start-Sleep -Milliseconds 250
        $ws.SendKeys('^n')
    }
}
"""
    subprocess.Popen(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                     creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)


class Monitor:
    def __init__(self):
        self.quotas = {}
        self.status = 'Leyendo cuotas...'
        self.next_switch = 0
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.switch_lock = threading.Lock()
        self.quota_wakeup = threading.Event()
        self.icon = pystray.Icon(
            'monitor_cuota', tray_image(None), 'Cuota Codex: leyendo ambas cuentas...',
            menu=pystray.Menu(
                pystray.MenuItem('Cambiar cuenta ahora', self.request_switch),
                pystray.MenuItem('Reanudar cambios automaticos', self.resume_automatic),
                pystray.MenuItem('Nuevo chat', self.new_chat),
                pystray.MenuItem('Salir', self.exit)))

    def notify(self, message):
        try:
            self.icon.notify(message, 'Cuota Codex')
        except Exception:
            logging.exception('No se pudo mostrar la notificacion de Windows')

    def request_switch(self, icon=None, item=None, *, reason='manual'):
        if reason == 'automatico' and rotation_blocked():
            return
        if not self.switch_lock.acquire(blocking=False):
            self.notify('Ya hay un cambio de cuenta en curso')
            return
        active = active_account()
        if active not in (1, 2):
            self.switch_lock.release()
            self.notify('No se pudo identificar la cuenta activa')
            logging.error('ROTACION rechazada: cuenta activa desconocida')
            return
        self.status = f'Cambiando a cuenta {3 - active}...'
        logging.info('ROTACION solicitud inmediata motivo=%s C%s -> C%s', reason, active, 3 - active)
        self.notify(self.status)
        self.next_switch = time.time() + 120
        threading.Thread(target=self.perform_switch, args=(active, 3-active, reason),
                         daemon=True, name='rotacion').start()

    def perform_switch(self, active, destination, reason):
        try:
            switch_account(active, destination, reason)
            with self.lock:
                self.quotas.clear()
            self.status = f'Cuenta {destination} activa'
            self.notify(self.status)
        except Exception:
            block_rotation('Fallo de rotacion; requiere reanudacion manual desde la bandeja')
            logging.exception('ROTACION ERROR motivo=%s C%s -> C%s', reason, active, destination)
            self.status = 'Cambio fallido; automatico pausado (sin reintentos)'
            self.notify(self.status)
        finally:
            self.switch_lock.release()
            self.quota_wakeup.set()

    def check_automatic(self):
        if rotation_blocked():
            return
        active = active_account()
        with self.lock:
            quotas = dict(self.quotas)
        if time.time() >= self.next_switch and should_switch(active, quotas, latest_write(), time.time()):
            self.request_switch(reason='automatico')

    def resume_automatic(self, icon=None, item=None):
        ROTATION_STATE.unlink(missing_ok=True)
        self.next_switch = time.time() + 120
        self.status = 'Cambios automaticos reanudados; espera de 120 segundos'
        logging.info('ROTACION automatica reanudada manualmente')
        self.notify(self.status)

    def new_chat(self, icon=None, item=None):
        trigger_new_chat()

    def exit(self, icon=None, item=None):
        self.stopped.set()
        self.quota_wakeup.set()
        self.icon.stop()

    def quota_worker(self):
        while not self.stopped.is_set():
            self.quota_wakeup.clear()
            for number in (1, 2):
                try:
                    quota = fetch_quota(number)
                    with self.lock:
                        self.quotas[number] = quota
                except Exception as exc:
                    logging.warning('Cuota C%s: %s', number, type(exc).__name__)
            self.quota_wakeup.wait(QUOTA_INTERVAL)

    def worker(self):
        next_cleanup = 0
        try:
            desktop_target()  # Cache discovery before a user requests a switch.
        except Exception:
            logging.exception('No se pudo precargar el lanzador de Codex')
        while not self.stopped.is_set():
            try:
                self.check_automatic()
                if time.time() >= next_cleanup:
                    cleanup_old_chats()
                    next_cleanup = time.time() + 3600
            except Exception:
                logging.exception('Monitor: error de rotacion automatica o limpieza')
            self.stopped.wait(1)

    def refresh(self):
        while not self.stopped.is_set():
            try:
                with self.lock:
                    quotas = dict(self.quotas)
                title, value = tray_summary(active_account(), quotas, time.time())
                self.icon.title = title
                self.icon.icon = tray_image(value)
            except Exception as exc:
                logging.error('Bandeja: %s', type(exc).__name__)
            self.stopped.wait(5)

    def setup(self, icon):
        icon.visible = True
        threading.Thread(target=self.worker, daemon=True, name='rotacion-automatica').start()
        threading.Thread(target=self.quota_worker, daemon=True, name='cuotas').start()
        threading.Thread(target=self.refresh, daemon=True, name='bandeja').start()
        logging.info('Monitor iniciado en la bandeja del sistema')

    def run(self):
        try:
            self.icon.run(setup=self.setup)
        finally:
            self.stopped.set()


if __name__ == '__main__':
    Monitor().run()
