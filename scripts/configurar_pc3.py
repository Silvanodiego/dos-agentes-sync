"""Configuracion inicial v7. No importa tokens ni bases de datos de otra PC."""
from __future__ import annotations

import argparse
from contextlib import closing
import importlib.util
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import tomllib

import tomlkit


def expand(value, home: Path, root: Path):
    if isinstance(value, str):
        value = value.replace('%USERPROFILE%', str(home)).replace('C:\\dos_agentes_local', str(root))
        for key in ('DOS_AGENTES_HOME', 'LOCALAPPDATA', 'DRIVE_ROOT', 'CODEX_APP_DIR'):
            if key == 'DOS_AGENTES_HOME':
                replacement = str(root)
            else:
                replacement = os.environ.get(key, '')
            if replacement:
                value = value.replace('%' + key + '%', replacement.replace('\\', '/'))
        return value
    if isinstance(value, list):
        return [expand(item, home, root) for item in value]
    if isinstance(value, dict):
        return {expand(key, home, root): expand(item, home, root) for key, item in value.items()}
    return value


def render_config(template: str, existing: str | None, home: Path, root: Path) -> str:
    base = expand(tomllib.loads(template), home, root)
    if existing is None:
        doc = tomlkit.document()
        doc.update(base)
    else:
        # Ambos parsers rechazan claves duplicadas. No se reescribe un TOML invalido.
        tomllib.loads(existing)
        doc = tomlkit.parse(existing)
        if 'mcp_servers' not in doc:
            doc['mcp_servers'] = tomlkit.table()
        doc['mcp_servers']['antigravity_bridge'] = base['mcp_servers']['antigravity_bridge']
        if 'projects' not in doc:
            doc['projects'] = tomlkit.table()
        doc['projects'][str(root)] = {'trust_level': 'trusted'}
    result = tomlkit.dumps(doc)
    parsed = tomllib.loads(result)
    assert parsed['mcp_servers']['antigravity_bridge']['enabled'] is True
    assert '%USERPROFILE%' not in str(parsed['mcp_servers']['antigravity_bridge'])
    return result


def initialize_databases(root: Path):
    # Solo esquemas, sin cuentas, historial ni colas de la PC 1.
    schema = Path(__file__).with_name('esquemas_pc3.py')
    spec = importlib.util.spec_from_file_location('esquemas_pc3', schema)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for relative, statements in module.SCHEMAS.items():
        target = root / relative
        if target.exists():
            continue  # Conservar todas las bases existentes en una reinstalacion.
        target.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(target)) as conn:
            with conn:
                conn.executescript(statements)


def configure(root: Path, home: Path):
    root = root.resolve()
    shared = root / 'config_compartida'
    codex = home / '.codex'
    codex.mkdir(parents=True, exist_ok=True)
    target = codex / 'config.toml'
    template = root / 'config.toml'
    if template.is_file():
        sys.path.insert(0, str(Path(__file__).parent))
        from restaurar_ecosistema_pc3 import restore, values
        replacements = values(home, root)
        os.environ.update(replacements)
        restore(root, home, replacements)
    else:
        template = shared / 'config.toml'
    result = render_config(template.read_text(encoding='utf-8-sig'),
                           target.read_text(encoding='utf-8-sig') if target.exists() else None,
                           home, root)
    target.write_text(result, encoding='utf-8')
    rules = (shared / 'AGENTS.md').read_bytes()
    (codex / 'AGENTS.md').write_bytes(rules)
    (root / 'AGENTS.md').write_bytes(rules)
    # auth.json no viaja en el ZIP: se crea desde la exportacion de la cuenta 1.
    if not (codex / 'auth.json').exists() and (root / 'auth_c1.json').is_file():
        (codex / 'auth.json').write_bytes((root / 'auth_c1.json').read_bytes())
    scripts = home / 'ScriptsGlobales'
    scripts.mkdir(parents=True, exist_ok=True)
    for name in ('agy.bat', 'antigravity_mcp.bat'):
        content = (shared / name).read_text(encoding='utf-8-sig')
        content = content.replace('C:\\dos_agentes_local', str(root))
        (scripts / name).write_text(content, encoding='utf-8', newline='\r\n')
    agent = home / '.antigravity-agent'
    agent.mkdir(parents=True, exist_ok=True)
    token = agent / 'local_bridge_token'
    if not token.exists():
        token.write_text(secrets.token_hex(32), encoding='utf-8')
    gui = agent / 'gui_config.json'
    settings = json.loads(gui.read_text(encoding='utf-8-sig')) if gui.exists() else {}
    proxy = settings.setdefault('proxy', {})
    proxy.setdefault('host', '127.0.0.1')
    proxy.setdefault('port', 8045)
    proxy['enabled'] = True
    proxy.setdefault('auto_start', True)
    gui.write_text(json.dumps(settings, indent=2), encoding='utf-8')
    initialize_databases(root)
    print('TOML valido, MCP antigravity_bridge habilitado; credenciales locales nuevas, DB vacias.', flush=True)


def start_services(root: Path):
    sys.path.insert(0, str(root / 'scripts'))
    spec = importlib.util.spec_from_file_location('sync_git', root / 'scripts/sync_git.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.start_services()
    print('Cascada AG 8765, panel 8787 y monitor iniciados. Sin inferencias de prueba.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--iniciar', action='store_true')
    args = parser.parse_args()
    if args.iniciar:
        start_services(args.root)
    else:
        configure(args.root, args.home)
