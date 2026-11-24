"""Replica historiales con Codex abierto; importa versiones nuevas sin sobrescribir chats."""
from __future__ import annotations

import argparse
import base64
from contextlib import closing
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
import uuid

from backup_chats import _snapshot_sqlite, _snapshot_jsonl
from coverage_chats import normalize_windows_path

TABLES = ('thread_turns', 'thread_items', 'thread_realtime_items', 'thread_history_projection_state')
MAX_OBJECT = 256 * 1024 * 1024
FORMAT = 'codex-live-history-v1'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def history_fingerprint(tables, rollout):
    return digest(encoded({'tables': tables, 'rollout': rollout}))


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.partial')
    with temporary.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def rows(db, table, thread_id):
    # table is always selected from the constant allowlist, never from a bundle.
    return sorted([dict(r) for r in db.execute('SELECT * FROM ' + table + ' WHERE thread_id=?', (thread_id,))], key=encoded)


def dbpath(home, pattern):
    files = list(home.glob(pattern))
    if len(files) != 1 or files[0].is_symlink():
        raise ValueError('Se requiere una unica base regular: ' + pattern)
    return files[0]


def read_object(cloud, key):
    if not re.fullmatch('[a-f0-9]{64}', key):
        raise ValueError('Hash de objeto invalido')
    path = cloud / 'objects' / (key + '.json.gz')
    if path.is_symlink():
        raise ValueError('Objeto enlazado rechazado')
    with gzip.open(path, 'rb') as stream:
        data = stream.read(MAX_OBJECT + 1)
    if len(data) > MAX_OBJECT or digest(data) != key:
        raise ValueError('Objeto incompleto, excesivo o alterado')
    result = json.loads(data)
    if result.get('format') != FORMAT:
        raise ValueError('Formato de objeto desconocido')
    return result


def publish_package(cloud, package):
    data = encoded(package)
    if len(data) > MAX_OBJECT:
        raise ValueError('Historial excede el limite por objeto')
    key = digest(data)
    output = cloud / 'objects' / (key + '.json.gz')
    if output.exists():
        read_object(cloud, key)
    else:
        atomic(output, gzip.compress(data, compresslevel=6, mtime=0))
    return key


def export_live(home, cloud, machine, state, temporary):
    # Only allowlisted conversation DB tables are published, never whole DBs.
    source_state = dbpath(home, 'state_[0-9]*.sqlite')
    source_history = dbpath(home, 'thread_history_[0-9]*.sqlite')
    deadline = time.monotonic() + 240
    _snapshot_sqlite(source_state, temporary / 'state.sqlite', deadline)
    _snapshot_sqlite(source_history, temporary / 'history.sqlite', deadline)
    baselines = state.get('import_baselines', {})
    manifest = {'format': FORMAT, 'machine': machine,
                'created_at': datetime.now(timezone.utc).isoformat(), 'chats': []}
    published = 0
    ready = missing = generating = 0
    with closing(sqlite3.connect(temporary / 'state.sqlite')) as db, \
         closing(sqlite3.connect(temporary / 'history.sqlite')) as history:
        db.row_factory = history.row_factory = sqlite3.Row
        for row in db.execute("SELECT * FROM threads ORDER BY id"):
            thread = dict(row)
            thread_id = thread['id']
            if (thread.get('thread_source') not in (None, 'user', 'agent_created_thread') or
                thread.get('attached_thread_parent_id') or
                thread.get('source') not in ('vscode', 'cli', 'exec') or
                not (thread.get('first_user_message') or thread.get('preview'))):
                continue
            tables = {name: rows(history, name, thread_id) for name in TABLES}
            turns = tables['thread_turns']
            latest = max(turns, key=lambda t: t['rollout_ordinal'], default=None)
            busy = bool(latest and latest['status'].replace('_', '').lower() in
                        ('inprogress', 'running', 'pending', 'started'))
            package = {'format': FORMAT, 'machine': machine, 'thread': thread,
                       'tables': tables, 'rollout': None, 'busy': busy,
                       'source_profile': str(home.parent)}
            rollout = Path(normalize_windows_path(thread['rollout_path']))
            if rollout.suffix == '.jsonl' and rollout.is_file() and not rollout.is_symlink():
                resolved = rollout.resolve()
                roots = [home / 'sessions', home / 'archived_sessions']
                if not any(resolved.is_relative_to(r.resolve()) for r in roots):
                    # Old imports can refer to someone else's profile. Preserve
                    # their SQLite history without reading outside this home.
                    manifest['chats'].append({'id': thread_id, 'object': publish_package(cloud, package)})
                    missing += 1
                    continue
                if rollout.stat().st_size > MAX_OBJECT // 2:
                    raise ValueError('Rollout excede el limite de copia: ' + thread_id)
                target = temporary / 'rollout.jsonl'
                target.unlink(missing_ok=True)
                record = _snapshot_jsonl(rollout, target, deadline)
                package['rollout'] = base64.b64encode(target.read_bytes()).decode('ascii')
                package['busy'] = busy or not record['last_line_terminated']
            # An untouched replica must not echo back. A continued replica IS
            # a new local branch and must be published to the other PCs.
            fingerprint = history_fingerprint(tables, package['rollout'])
            if baselines.get(thread_id) == fingerprint:
                continue
            data = encoded(package)
            if len(data) > MAX_OBJECT:
                raise ValueError('Historial excede el limite por objeto: ' + thread_id)
            key = digest(data)
            output = cloud / 'objects' / (key + '.json.gz')
            if not output.exists():
                atomic(output, gzip.compress(data, compresslevel=6, mtime=0))
                published += 1
            manifest['chats'].append({'id': thread_id, 'object': key})
            if package['rollout'] is None:
                missing += 1
            elif package['busy']:
                generating += 1
            else:
                ready += 1
    atomic(cloud / 'machines' / (machine + '.json'), encoded(manifest))
    return {'exported_chats': len(manifest['chats']), 'new_objects': published,
            'ready_versions': ready, 'archived_sqlite_only': missing,
            'generating_versions': generating, 'transport': 'Drive; subida remota no verificada'}


def columns(db, table):
    return [r[1] for r in db.execute('PRAGMA table_info(' + table + ')')]


def insert_row(db, table, row):
    names = columns(db, table)
    if set(names) != set(row):
        raise ValueError('Version de esquema incompatible: ' + table)
    quoted = ','.join('"' + n.replace('"', '""') + '"' for n in names)
    db.execute('INSERT INTO ' + table + ' (' + quoted + ') VALUES (' + ','.join('?' for _ in names) + ')',
               [row[n] for n in names])


def validate_rollout(raw, source_id, new_id):
    if not raw or not raw.endswith(b'\n'):
        raise ValueError('Rollout sin ultima linea completa')
    lines = raw.splitlines(keepends=True)
    first = json.loads(lines[0])
    if first.get('type') != 'session_meta' or first.get('payload', {}).get('id') != source_id:
        raise ValueError('Identidad del rollout no coincide')
    # Preserve every byte offset stored by the native history projection.
    pattern = rb'("(?:id|session_id)"\s*:\s*")' + source_id.encode('ascii') + rb'(")'
    lines[0], count = re.subn(pattern, lambda m: m[1] + new_id.encode('ascii') + m[2], lines[0])
    if count < 1 or len(source_id) != len(new_id):
        raise ValueError('No se puede conservar los offsets del rollout')
    for line in lines[1:]:
        json.loads(line)  # validate every complete JSON record, no evaluation
    return b''.join(lines)


def import_version(home, package, key, ledger, default_cwd, baselines=None):
    """New IDs only: no update/delete of any existing local thread or history."""
    if package['busy'] or package['rollout'] is None:
        return 'preserved_only'
    source = package['thread']
    source_id = str(uuid.UUID(source['id']))
    # Deterministic version ID: repeat runs and interrupted imports are idempotent.
    new_id = str(uuid.uuid5(uuid.NAMESPACE_URL, FORMAT + ':' + package['machine'] + ':' + source_id + ':' + key))
    state_path = dbpath(home, 'state_[0-9]*.sqlite')
    history_path = dbpath(home, 'thread_history_[0-9]*.sqlite')
    stamp = datetime.fromtimestamp(source['created_at'], timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')
    rollout = home / 'sessions' / 'sync' / ('rollout-' + stamp + '-' + new_id + '.jsonl')
    raw = (validate_rollout(base64.b64decode(package['rollout'], validate=True), source_id, new_id)
           if package['rollout'] is not None else None)
    expected_tables = {table: sorted([dict(row, thread_id=new_id) for row in package['tables'][table]], key=encoded) for table in TABLES}
    baseline = history_fingerprint(expected_tables, base64.b64encode(raw).decode('ascii') if raw else None)
    thread = dict(source, id=new_id, rollout_path=str(rollout), is_pinned=0,
                  project_id=None, thread_section_id=None, attached_thread_parent_id=None)
    thread['name'] = (source.get('name') or source['title']) + ' [sync ' + package['machine'] + ']'
    if not Path(thread['cwd']).is_dir():
        thread['cwd'] = str(default_cwd)
    # Stage file first, history second, visibility row last. A crash can leave
    # an invisible staged replica, never a half-replaced existing conversation.
    with closing(sqlite3.connect(state_path, timeout=5)) as db, \
         closing(sqlite3.connect(history_path, timeout=5)) as history:
        existing = db.execute('SELECT rollout_path FROM threads WHERE id=?', (new_id,)).fetchone()
        if existing:
            if str(rollout) != existing[0]:
                raise ValueError('Colision de identidad; no se modifica el chat existente')
            ledger.add(new_id)
            if baselines is not None:
                baselines.setdefault(new_id, baseline)
            return 'already_imported'
        if set(columns(db, 'threads')) != set(thread):
            raise ValueError('Version de esquema incompatible: threads')
        for table in TABLES:
            for row in package['tables'][table]:
                if row.get('thread_id') != source_id or set(columns(history, table)) != set(row):
                    raise ValueError('Esquema/identidad de historial incompatible')
        if raw is None:
            pass  # Native paginated histories live in SQLite, not JSONL.
        elif rollout.exists():
            if rollout.read_bytes() != raw:
                raise ValueError('Se conserva el rollout local diferente')
        else:
            atomic(rollout, raw)
        with history:
            # Only a deterministic ID absent from the threads table is resumed
            # after a crash. Verify, never overwrite previously staged rows.
            history.row_factory = sqlite3.Row
            for table in TABLES:
                expected = [dict(row, thread_id=new_id) for row in package['tables'][table]]
                previous = rows(history, table, new_id)
                if previous:
                    if sorted(map(encoded, previous)) != sorted(map(encoded, expected)):
                        raise ValueError('Historial staged diferente; conservado')
                else:
                    for row in expected:
                        insert_row(history, table, row)
        with db:
            insert_row(db, 'threads', thread)
        ledger.add(new_id)
        if baselines is not None:
            baselines[new_id] = baseline
    return 'imported'


def sync_once(home, cloud, machine, state_path, default_cwd):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', machine):
        raise ValueError('Identificador de PC invalido')
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    imported = set(state.get('imported_ids', []))
    accepted = set(state.get('accepted_objects', []))
    baselines = state.setdefault('import_baselines', {})
    result = {'status': 'synchronized_live', 'requires_codex_closed': False,
              'imported_versions': 0, 'preserved_only': 0, 'pending_objects': 0}
    # Persist replica ownership before exporting so imports are never re-exported.
    for manifest_path in sorted((cloud / 'machines').glob('*.json')):
        if manifest_path.stem == machine:
            continue
        try:
            manifest = json.loads(manifest_path.read_bytes())
            if manifest['format'] != FORMAT or manifest['machine'] != manifest_path.stem:
                raise ValueError('Manifiesto incompatible')
            for chat in manifest['chats']:
                key = chat['object']
                if key in accepted:
                    continue
                try:
                    package = read_object(cloud, key)
                    if package['machine'] != manifest['machine'] or package['thread']['id'] != chat['id']:
                        raise ValueError('Objeto no coincide con manifiesto')
                    status = import_version(home, package, key, imported, default_cwd, baselines)
                    if status in ('imported', 'already_imported'):
                        accepted.add(key)
                        result['imported_versions'] += status == 'imported'
                    else:
                        result['preserved_only'] += 1
                    state.update(imported_ids=sorted(imported), accepted_objects=sorted(accepted))
                    atomic(state_path, encoded(state))
                except (OSError, ValueError, EOFError, KeyError, sqlite3.Error) as exc:
                    result['pending_objects'] += 1
                    result['last_pending_reason'] = type(exc).__name__ + ': ' + str(exc)
        except (OSError, ValueError, KeyError) as exc:
            result['pending_objects'] += 1
            result['last_pending_reason'] = type(exc).__name__ + ': ' + str(exc)
    with tempfile.TemporaryDirectory(prefix='codex-live-') as temporary:
        result.update(export_live(home, cloud, machine, state, Path(temporary)))
    result['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
    if result['pending_objects']:
        result['status'] = 'partial_live'
    atomic(state_path.with_name('live-sync-status.json'), encoded(result))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--home', type=Path, default=Path.home() / '.codex')
    p.add_argument('--cloud', type=Path, required=True)
    p.add_argument('--machine', required=True)
    p.add_argument('--state', type=Path, required=True)
    p.add_argument('--default-cwd', type=Path, default=Path('C:/dos_agentes_local'))
    args = p.parse_args()
    args.state.parent.mkdir(parents=True, exist_ok=True)
    import msvcrt
    with args.state.with_suffix('.lock').open('a+b') as lock:
        lock.seek(0)
        lock.write(b'0')
        lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        try:
            print(json.dumps(sync_once(args.home.resolve(), args.cloud.resolve(), args.machine,
                                       args.state.resolve(), args.default_cwd.resolve())))
        except Exception as exc:
            error = {'status': 'blocked', 'error': str(exc),
                     'checked_at_utc': datetime.now(timezone.utc).isoformat()}
            atomic(args.state.with_name('live-sync-status.json'), encoded(error))
            raise


if __name__ == '__main__':
    main()
