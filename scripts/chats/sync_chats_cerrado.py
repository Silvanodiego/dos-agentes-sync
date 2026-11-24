"""Sincronizacion silenciosa en frio; nunca cierra Codex ni importa SQLite."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import sqlite3
import tempfile
import tomllib

from coverage_chats import (CoverageError, audit_source, classify_rollout,
                            locate_database, read_threads)


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verified_file(record):
    path = Path(record['path'])
    if path.is_symlink() or not path.is_file() or sha256(path) != record['sha256']:
        raise ValueError('Archivo de recuperacion alterado o ausente: ' + str(path))
    return path


def coverage(home):
    try:
        return audit_source(home)
    except CoverageError as exc:
        if 'WAL_WITHOUT_SHM' not in str(exc):
            raise
    # On clean shutdown SQLite removes WAL/SHM but retains the WAL header.
    # Inspect a verified detached copy instead of letting SQLite create SHM in
    # the real home. A remaining or newly appearing WAL always blocks this path.
    database, _ = locate_database(home)
    wal = database.with_name(database.name + '-wal')
    if wal.exists():
        raise CoverageError('WAL sin SHM: se conserva la fuente sin abrirla')
    before = database.stat()
    with tempfile.TemporaryDirectory(prefix='codex-coverage-') as temporary:
        detached = Path(temporary) / database.name
        shutil.copyfile(database, detached)
        after = database.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or wal.exists():
            raise CoverageError('La base cambio durante la copia de lectura')
        if sha256(database) != sha256(detached) or wal.exists():
            raise CoverageError('La copia de lectura no coincide con la fuente')
        with closing(sqlite3.connect(detached)) as connection:
            if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise CoverageError('Copia SQLite inconsistente')
            connection.execute('PRAGMA journal_mode=DELETE')
        rows, _ = read_threads(detached)
        for row in rows:
            row.update(classify_rollout(row['rollout_path'], home))
        return {'missing': [row for row in rows if row['coverage'] == 'missing']}


def check_coverage(home, acceptance=None):
    report = coverage(home)
    missing = {r['thread_id'] for r in report['missing']}
    if not missing:
        return
    if acceptance is None:
        raise ValueError('Hay sesiones sin rollout y sin recuperacion verificada')
    policy = json.loads(acceptance.read_text(encoding='utf-8'))
    if policy.get('format') != 1 or not missing.issubset(set(policy['known_missing'])):
        raise ValueError('Hay sesiones NUEVAS sin rollout; se conserva todo y se suspende la sincronizacion')
    # The old missing rollouts remain missing. Their data is explicitly preserved,
    # not silently declared resumable or filtered using has_user_event=0.
    index_path = verified_file(policy['recovery_index'])
    for chat in json.loads(index_path.read_text(encoding='utf-8'))['chats']:
        for name, digest in ((chat['raw_file'], chat['raw_sha256']),
                             (chat['history_file'], chat['history_sha256'])):
            path = index_path.parent / name
            if path.parent != index_path.parent:
                raise ValueError('Ruta de recuperacion fuera de su carpeta')
            verified_file({'path': str(path), 'sha256': digest})
    mapping = json.loads(verified_file(policy['continuations']).read_text(encoding='utf-8'))
    if isinstance(mapping, dict):
        mapping = mapping['chats']
    indexed = {c['id'] for c in json.loads(index_path.read_text(encoding='utf-8'))['chats']}
    if {c['original_id'] for c in mapping} != indexed:
        raise ValueError('Faltan continuaciones recuperadas')
    for chat in mapping:
        candidates = (p for folder in ('sessions', 'archived_sessions')
                      for p in (home / folder).rglob('*' + chat['threadId'] + '.jsonl*'))
        if not any(p.is_file() and not p.is_symlink() and p.suffix in ('.jsonl', '.zst', '.gz', '.xz')
                   for p in candidates):
            raise ValueError('Falta el rollout nativo de una continuacion')
    verified_file(policy['portable_backup'])


def validate_config(root):
    manifest = json.loads((root / 'vendor_manifest.json').read_text(encoding='utf-8'))
    for name, digest in manifest.items():
        if sha256(root / 'vendor' / name) != digest:
            raise ValueError('Core auditado modificado: ' + name)
    config = tomllib.loads((root / 'codexsync.toml').read_text(encoding='utf-8'))
    required = {'sync': {'mode': 'cold', 'direction': 'bidirectional', 'scope': 'full',
                        'session_mode': 'all', 'delete_policy': 'never', 'close_codex': False},
                'safety': {'require_codex_stopped': True, 'fail_on_unknown': True},
                'process_detection': {'allow_terminate_if_running': False},
                'targets': {'include_roots': ['sessions', 'archived_sessions', 'session_index.jsonl']}}
    for section, values in required.items():
        if any(config.get(section, {}).get(k) != v for k, v in values.items()):
            raise ValueError('Configuracion fuera del perfil seguro: ' + section)
    return Path(config['paths']['local_state_dir']).expanduser()


def execute(root, acceptance, python):
    home = validate_config(root)
    check_coverage(home, acceptance)
    command = [str(python), str(root / 'codexsync.py'), '-c', str(root / 'codexsync.toml'),
               'sync', '--apply', '--unattended', '--conflict-policy', 'manual_abort']
    logs = root / 'logs'
    logs.mkdir(exist_ok=True)
    with (logs / 'automatic-sync.log').open('a', encoding='utf-8') as output:
        output.write('\n' + datetime.now(timezone.utc).isoformat() + '\n')
        output.flush()
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    statuses = {0: 'synchronized', 2: 'conflict_preserved', 3: 'waiting_codex_closed'}
    return {'status': statuses.get(result.returncode, 'core_error'), 'exit_code': result.returncode}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-root', type=Path, default=Path(os.environ['LOCALAPPDATA']) / 'CodexSync')
    parser.add_argument('--acceptance', type=Path)
    args = parser.parse_args()
    root = args.install_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    # Kernel lock releases even after a crash; no stale-file deletion or overlap.
    import msvcrt
    with (root / 'automatic-sync.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        try:
            status = execute(root, args.acceptance, Path(sys.executable))
        except Exception as exc:
            status = {'status': 'blocked', 'error': str(exc)}
        status['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
        temporary = root / 'automatic-sync-status.tmp'
        temporary.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(root / 'automatic-sync-status.json')
        print(json.dumps(status, ensure_ascii=False))


if __name__ == '__main__':
    main()
