"""Activa chats al estar disponibles Drive y las bases nativas; no cierra Codex."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time


def wait_for_sync(path, started_at, timeout=60):
    """Exige un resultado reciente del worker, no solo registrar una tarea."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            result = json.loads(path.read_text(encoding='utf-8-sig'))
            checked = datetime.fromisoformat(result['checked_at_utc'])
            if checked >= started_at:
                if result.get('status') != 'synchronized_live':
                    return False, json.dumps(result, ensure_ascii=False)
                return True, json.dumps(result, ensure_ascii=False)
        except (OSError, ValueError, KeyError, TypeError):
            pass
        if time.monotonic() >= deadline:
            return False, 'La tarea fue registrada, pero no produjo una sincronizacion reciente verificable. Revise live-sync-status.json y LastTaskResult de CodexChatsSyncLive.'
        time.sleep(1)


def activate(root, status, runner=subprocess.run, verifier=wait_for_sync):
    command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
               str(root / 'scripts/chats/activar_sync_abierto.ps1'),
               '-PythonExecutable', str(root / '.venv/Scripts/pythonw.exe')]
    env = dict(os.environ)
    env.pop('PSModulePath', None)
    options = dict(capture_output=True, text=True, errors='replace', timeout=100,
                   env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        started_at = datetime.now(timezone.utc)
        result = runner(command, **options)
        state = {'status': 'pending',
                 'detail': (result.stdout + result.stderr)[-6000:]}
        if result.returncode == 0:
            healthy, detail = verifier(status.with_name('live-sync-status.json'), started_at)
            state['status'] = 'activated' if healthy else 'pending'
            state['detail'] += '\nPrimera sincronizacion: ' + detail
    except (OSError, subprocess.TimeoutExpired) as error:
        state = {'status': 'pending', 'detail': str(error)}
    state['checked_at'] = datetime.now(timezone.utc).isoformat()
    status.parent.mkdir(parents=True, exist_ok=True)
    status.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    if state['status'] == 'activated':
        # El worker principal ya esta activo. No volver a registrarlo cada dos minutos.
        runner(['powershell.exe', '-NoProfile', '-Command',
                "Disable-ScheduledTask -TaskName 'CodexChatsAutoSetup' -ErrorAction SilentlyContinue | Out-Null"],
               **options)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    status = Path(os.environ['LOCALAPPDATA']) / 'CodexSync/activation-status.json'
    state = activate(args.root, status)
    print(state['status'] + ': ' + state['detail'])
