"""Activa chats al estar disponibles Drive y las bases nativas; no cierra Codex."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess


def activate(root, status, runner=subprocess.run):
    command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
               str(root / 'scripts/chats/activar_sync_abierto.ps1'),
               '-PythonExecutable', str(root / '.venv/Scripts/pythonw.exe')]
    env = dict(os.environ)
    env.pop('PSModulePath', None)
    options = dict(capture_output=True, text=True, errors='replace', timeout=100,
                   env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    try:
        result = runner(command, **options)
        state = {'status': 'activated' if result.returncode == 0 else 'pending',
                 'detail': (result.stdout + result.stderr)[-6000:]}
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
