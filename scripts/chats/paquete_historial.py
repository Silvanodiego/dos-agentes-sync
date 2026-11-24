"""Exporta un respaldo verificado a un ZIP portable; no importa ni sincroniza bases."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import zipfile

STATE = {'_sqlx_migrations', 'threads', 'projects', 'project_roots',
         'project_idempotency_keys', 'thread_sections', 'thread_attachments',
         'thread_dynamic_tools', 'thread_read_receipts', 'thread_spawn_edges',
         'guardian_review_feedback', 'session_model_ids'}
HISTORY = {'_sqlx_migrations', 'thread_history_projection_state', 'thread_items',
           'thread_realtime_items', 'thread_turns'}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def sanitized(source, target, allowed):
    # Only an already verified, private backup is accepted by the caller.
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src:
        with closing(sqlite3.connect(target)) as dst:
            for name, sql in src.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"):
                if name not in allowed:
                    continue
                dst.execute(sql)
                quoted = '"' + name.replace('"', '""') + '"'
                rows = src.execute('SELECT * FROM ' + quoted)
                count = len(rows.description)
                dst.executemany('INSERT INTO ' + quoted + ' VALUES (' + ','.join('?' * count) + ')', rows)
            dst.commit()
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('SQLite no supera integrity_check')


def export(source, output):
    source = source.resolve(strict=True)
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('status') != 'verified':
        raise ValueError('Se requiere un respaldo verificado')
    # Validate every source member before publishing anything.
    members = []
    for record in manifest['files']:
        relative = Path(record['path'])
        path = (source / relative).resolve(strict=True)
        if not path.is_relative_to(source) or path.is_symlink() or digest(path) != record['sha256']:
            raise ValueError('Integridad o ruta no valida en el respaldo')
        if relative.parts[0] in ('sessions', 'archived_sessions') or relative.as_posix() == 'session_index.jsonl':
            members.append((path, relative.as_posix()))
    output = output.absolute()
    if output.is_relative_to(source) or output.exists():
        raise ValueError('El ZIP debe ser nuevo y externo al respaldo')
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {'format': 'dos-agentes-history-archive-v1', 'source_created_at': manifest['created_at'],
              'native_resume_verified': False, 'automatic_import': False,
              'warning': 'Archivo de preservacion; no equivale a sincronizacion ni repara rollouts faltantes.',
              'files': []}
    with tempfile.TemporaryDirectory(prefix='codex-history-export-') as temp:
        stage = Path(temp)
        for name, allowed in [('state_5.sqlite', STATE), ('thread_history_1.sqlite', HISTORY)]:
            original = source / name
            if not any(r['path'] == name for r in manifest['files']):
                raise ValueError('Falta base verificada: ' + name)
            sanitized(original, stage / name, allowed)
            members.append((stage / name, 'databases/' + name))
        with closing(sqlite3.connect((stage / 'state_5.sqlite').as_uri() + '?mode=ro', uri=True)) as db:
            report['threads'] = db.execute('SELECT count(*) FROM threads').fetchone()[0]
        with closing(sqlite3.connect((stage / 'thread_history_1.sqlite').as_uri() + '?mode=ro', uri=True)) as db:
            report['history_items'] = db.execute('SELECT count(*) FROM thread_items').fetchone()[0]
        # Exclusive creation: an existing archive can never be replaced.
        with output.open('xb') as stream:
            with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for path, name in members:
                    report['files'].append({'path': name, 'sha256': digest(path), 'bytes': path.stat().st_size})
                    archive.write(path, name)
                archive.writestr('manifest.json', json.dumps(report, ensure_ascii=False, indent=2))
        with zipfile.ZipFile(output) as archive:
            if archive.testzip() is not None:
                raise ValueError('ZIP corrupto')
            for record in report['files']:
                with archive.open(record['path']) as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != record['sha256']:
                        raise ValueError('Hash ZIP incorrecto')
    return {'zip': str(output), 'sha256': digest(output), 'files': len(members),
            'threads': report['threads'], 'history_items': report['history_items'],
            'native_resume_verified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.source, args.output), ensure_ascii=False))
