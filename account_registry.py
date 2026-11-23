"""Registro local de perfiles. No guarda tokens OAuth ni claves sin cifrar."""
import hashlib
import json
import os
import pathlib
import re
import threading
import uuid

ROOT = pathlib.Path(os.environ.get('CODEX_MANAGER_DATA', r'C:\dos_agentes_local\codex_manager'))
LOCK = threading.RLock()


def fingerprint(home):
    try:
        auth = json.loads((pathlib.Path(home) / 'auth.json').read_text(encoding='utf-8'))
        identity = auth.get('tokens', {}).get('account_id')
        return hashlib.sha256(identity.encode()).hexdigest()[:16] if identity else None
    except (OSError, ValueError, AttributeError):
        return None


def defaults():
    return {'version': 1, 'profiles': [
        {'id': 'coordinador', 'name': 'Codex coordinador', 'home': str(pathlib.Path.home() / '.codex'), 'builtin': True},
        {'id': 'ejecutor', 'name': 'Codex ejecutor', 'home': str(pathlib.Path.home() / '.cx/ejecutor'), 'builtin': True}],
        'providers': [], 'roles': {'coordinador': 'coordinador', 'ejecutor': 'ejecutor'}}


def load():
    with LOCK:
        path = ROOT / 'accounts.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else defaults()


def save(data):
    with LOCK:
        ROOT.mkdir(parents=True, exist_ok=True)
        tmp = ROOT / ('accounts.' + uuid.uuid4().hex + '.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, ROOT / 'accounts.json')


def checked_name(value):
    name = str(value).strip()
    if not name or len(name) > 80 or any(ord(c) < 32 for c in name):
        raise ValueError('Nombre obligatorio, hasta 80 caracteres.')
    return name


def get_profile(data, ident):
    return next((x for x in data['profiles'] if x['id'] == ident), None)


def role_homes():
    data = load()
    homes = {}
    for role in ('coordinador', 'ejecutor'):
        profile = get_profile(data, data['roles'][role])
        if not profile:
            raise ValueError('Perfil asignado inexistente: ' + role)
        homes[role] = pathlib.Path(profile['home'])
    return homes


def set_roles(coordinador, ejecutor):
    with LOCK:
        data = load()
        selected = [get_profile(data, ident) for ident in (coordinador, ejecutor)]
        if not all(selected):
            raise ValueError('Elegí dos perfiles existentes.')
        identities = [fingerprint(x['home']) for x in selected]
        if not all(identities) or identities[0] == identities[1]:
            raise ValueError('Se requieren dos cuentas Codex autenticadas distintas.')
        data['roles'] = {'coordinador': coordinador, 'ejecutor': ejecutor}
        save(data)
        return data['roles']


def add_profile(name):
    name = checked_name(name)
    with LOCK:
        data = load()
        ident = 'codex-' + uuid.uuid4().hex[:12]
        home = ROOT / 'profiles' / ident
        home.mkdir(parents=True)
        # Perfil nuevo: sandbox activo y sin reglas que creen equipos recursivos.
        (home / 'config.toml').write_text('sandbox_mode = "workspace-write"\n', encoding='utf-8')
        item = {'id': ident, 'name': name, 'home': str(home), 'builtin': False}
        data['profiles'].append(item)
        save(data)
        return item


def validate_model(value):
    value = str(value).strip()
    if not re.fullmatch(r'[A-Za-z0-9._:-]{1,120}', value):
        raise ValueError('Indicá un identificador de modelo válido.')
    return value
