"""Servicios locales del panel/monitor; no importa ni modifica Cascada AG."""
from __future__ import annotations
import ctypes
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
PYTHONW = ROOT / '.venv/Scripts/pythonw.exe'
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
ACTION_LOCK = threading.Lock()
_mutexes = []

def setup_logging(name):
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    (ROOT / 'logs').mkdir(exist_ok=True)
    handler = RotatingFileHandler(ROOT / 'logs' / (name + '.log'), maxBytes=1000000, backupCount=3, encoding='utf-8')
    logging.basicConfig(handlers=[handler], level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def singleton(name):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel.CreateMutexW(None, False, 'Local\\DosAgentes_' + name)
    error = ctypes.get_last_error()
    if not handle:
        raise ctypes.WinError(error)
    _mutexes.append(handle)
    return error != 183

def run(args, timeout=30):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, creationflags=NO_WINDOW)

def http_json(port, path):
    with OPENER.open(f'http://127.0.0.1:{port}{path}', timeout=3) as response:
        return json.load(response)

def cascada_status():
    services = {}
    for port, path in ((8765, '/health'), (8045, '/v1/models')):
        try:
            data = http_json(port, path)
            valid = data.get('status') == 'ready' if port == 8765 else isinstance(data.get('data'), list)
            services[str(port)] = {'ok': valid, 'detail': 'OK' if valid else 'Respuesta inválida'}
        except Exception as exc:
            services[str(port)] = {'ok': False, 'detail': str(exc)}
    failed = [port for port, value in services.items() if not value['ok']]
    return {'ok': not failed, 'detail': '8765 + 8045 OK' if not failed else 'Caído ' + ' y '.join(failed) + ' (posible causa de 502)', 'services': services}

def projects():
    with sqlite3.connect((ROOT / 'estado_puente.db').as_uri() + '?mode=ro', uri=True, timeout=2) as db:
        return [{'project': name, 'url': url} for name, url in db.execute('SELECT proyecto,url FROM config_chats ORDER BY proyecto') if urlsplit(url).scheme == 'https' and urlsplit(url).hostname == 'gemini.google.com']

def chat_status():
    result = {'ok': False, 'cdp': False, 'login_required': False, 'projects': []}
    try:
        result['projects'] = projects()
    except Exception as exc:
        result['projects_error'] = str(exc)
    try:
        version = http_json(9222, '/json/version')
        if not version.get('webSocketDebuggerUrl'):
            raise ValueError('CDP sin WebSocket')
        result['cdp'] = True
        pages = [p for p in http_json(9222, '/json/list') if p.get('type') == 'page']
        login = any(urlsplit(p.get('url', '')).hostname == 'accounts.google.com' for p in pages)
        gemini = any(urlsplit(p.get('url', '')).hostname == 'gemini.google.com' for p in pages)
        result.update(ok=gemini and not login, login_required=login, detail='Requiere login de Google' if login else 'CDP y pestaña Gemini OK' if gemini else 'CDP activo; falta pestaña Gemini')
    except Exception as exc:
        result['detail'] = '9222 caído: ' + str(exc)
    return result

def git_status():
    try:
        def git(*args):
            p = run(['git', *args], timeout=8)
            if p.returncode:
                raise RuntimeError(p.stderr.strip())
            return p.stdout.strip()
        ahead, behind = map(int, git('rev-list', '--left-right', '--count', 'HEAD...origin/main').split())
        return {'ok': ahead == behind == 0, 'branch': git('branch', '--show-current'), 'commit': git('log', '-1', '--format=%h %s'), 'ahead': ahead, 'behind': behind, 'detail': 'Al día con origin/main (último fetch local)' if ahead == behind == 0 else f'{ahead} por subir, {behind} por bajar', 'dirty': bool(git('status', '--porcelain'))}
    except Exception as exc:
        return {'ok': False, 'detail': str(exc)}

def errors_status():
    candidates = list((ROOT / 'logs').glob('*.log')) + list((ROOT / '.sync-local').glob('*.log')) + list(ROOT.glob('*.log'))
    infra = ROOT / 'errores_infra.md'
    if infra.exists():
        candidates.append(infra)
    lines = []
    for path in sorted(candidates, key=lambda p: p.stat().st_mtime):
        try:
            with path.open('rb') as f:
                f.seek(max(0, path.stat().st_size - 16384))
                tail = f.read().decode('utf-8', errors='replace').splitlines()[-25:]
            lines.extend(f'{path.name}: {line}' for line in tail)
        except OSError:
            pass
    # Nunca exportar credenciales conocidas en logs.
    import re
    return {'lines': [re.sub(r'(?i)(bearer\s+|(?:api[_-]?key|password|token)\s*[=:]\s*)\S+', r'\1[OCULTO]', line) for line in lines[-25:]]}

def start_panel():
    subprocess.Popen([str(PYTHONW), '-X', 'utf8', str(ROOT / 'panel_control.py')], cwd=ROOT, creationflags=NO_WINDOW)

def chrome_action(visible=False):
    # Solo cierra el perfil dedicado; nunca mata todos los chrome.exe.
    import re
    pattern = r'--user-data-dir=(?:"' + re.escape(str(ROOT / 'chrome_gemini_profile')) + r'"|' + re.escape(str(ROOT / 'chrome_gemini_profile')) + r')(?:\s|$)'
    script = "$p = Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'chrome.exe' -or $_.Name -eq 'msedge.exe') -and $_.CommandLine -match '" + pattern.replace("'", "''") + "' }; $p | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }"
    p = run(['powershell.exe', '-NoProfile', '-Command', script], timeout=15)
    if p.returncode:
        raise RuntimeError(p.stderr)
    time.sleep(1)
    bat = ROOT / ('abrir_chrome_gemini.bat' if visible else 'abrir_chrome_gemini_oculto.bat')
    p = run([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', str(bat)], timeout=25)
    if p.returncode:
        raise RuntimeError(p.stderr or f'Chrome terminó con {p.returncode}')
    return {'ok': True, 'detail': 'Chrome visible iniciado' if visible else 'Chrome oculto reiniciado'}

def action(name):
    if not ACTION_LOCK.acquire(blocking=False):
        return {'ok': False, 'detail': 'Otra acción está en curso'}
    try:
        if name == 'test-cascada':
            return cascada_status()
        if name in ('chrome-hidden', 'chrome-login'):
            return chrome_action(name == 'chrome-login')
        if name == 'git-pull':
            p = run(['git', 'pull', '--ff-only'], timeout=60)
            if p.returncode:
                logging.error('git pull: %s', p.stderr.strip())
            return {'ok': p.returncode == 0, 'detail': (p.stdout + p.stderr).strip()}
        return {'ok': False, 'detail': 'Acción desconocida'}
    except Exception as exc:
        logging.exception('Acción %s falló', name)
        return {'ok': False, 'detail': str(exc)}
    finally:
        ACTION_LOCK.release()
