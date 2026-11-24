"""Ascendencia causal y archivado reversible; nunca fusiona mensajes concurrentes."""
from contextlib import closing
import base64
import re
from pathlib import Path
import sqlite3
import time


def validate(package):
    lineage = package.get('lineage', {})
    logical = lineage.get('logical_id') or package['machine'] + ':' + package['thread']['id']
    ancestors = lineage.get('ancestors', [])
    if (not isinstance(logical, str) or len(logical) > 200 or
        not isinstance(ancestors, list) or len(ancestors) > 10000 or
        any(not isinstance(key, str) or not re.fullmatch('[a-f0-9]{64}', key) for key in ancestors)):
        raise ValueError('Ascendencia de chat invalida')
    return logical, ancestors


def identity(package, key, new_id, state):
    logical, ancestors = validate(package)
    state.setdefault('replica_lineage', {})[new_id] = {
        'logical_id': logical, 'key': key, 'ancestors': ancestors}


def export_lineage(thread_id, fingerprint, state, machine):
    previous = state.get('local_revisions', {}).get(thread_id)
    base = previous or state.get('replica_lineage', {}).get(thread_id)
    logical = base['logical_id'] if base else machine + ':' + thread_id
    ancestors = list(base.get('ancestors', [])) if base else []
    if base and base.get('fingerprint') != fingerprint:
        ancestors = list(dict.fromkeys(ancestors + [base['key']]))
    if len(ancestors) > 10000:
        raise ValueError('Limite de revisiones alcanzado; historial conservado')
    return {'logical_id': logical, 'ancestors': ancestors}


def remember_export(thread_id, fingerprint, key, lineage, state):
    state.setdefault('local_revisions', {})[thread_id] = dict(lineage, key=key, fingerprint=fingerprint)


def archive_superseded(home, state, live):
    """Archive only unchanged, completed ancestors. Divergent edits stay visible.

    Only the visibility flag changes: no rollout relocation or history rewriting.
    A still-open UI can retain its selection; that conversation remains resumable.
    """
    versions = dict(state.get('replica_lineage', {}))
    versions.update(state.get('local_revisions', {}))
    lineage = state.get('replica_lineage', {})
    if not lineage:
        return 0
    archived = 0
    with closing(sqlite3.connect(live.dbpath(home, 'state_[0-9]*.sqlite'), timeout=5)) as db, \
         closing(sqlite3.connect(live.dbpath(home, 'thread_history_[0-9]*.sqlite'), timeout=5)) as history:
        if 'archived' not in live.columns(db, 'threads'):
            return 0  # Older schemas have no reversible archive flag.
        history.row_factory = sqlite3.Row
        for tid, old in versions.items():
            newer = [value for other, value in lineage.items() if other != tid and
                     value['logical_id'] == old['logical_id'] and old['key'] in value['ancestors']]
            if not newer:
                continue
            row = db.execute('SELECT rollout_path,archived FROM threads WHERE id=?', (tid,)).fetchone()
            if row is None or row[1]:
                continue
            tables = {name: live.rows(history, name, tid) for name in live.TABLES}
            latest = max(tables['thread_turns'], key=lambda t: t['rollout_ordinal'], default=None)
            if latest and latest['status'].replace('_', '').lower() in ('inprogress', 'running', 'pending', 'started'):
                continue
            rollout = Path(live.normalize_windows_path(row[0]))
            try:
                if not rollout.resolve().is_relative_to(home.resolve()) or rollout.is_symlink():
                    continue
                raw = rollout.read_bytes()
                if not raw.endswith(b'\n'):
                    continue
            except OSError:
                continue
            fingerprint = live.history_fingerprint(tables, base64.b64encode(raw).decode('ascii'))
            expected = old.get('fingerprint') or state.get('import_baselines', {}).get(tid)
            if fingerprint != expected:
                continue
            with db:
                db.execute('UPDATE threads SET archived=1,archived_at=? WHERE id=? AND archived=0', (int(time.time()), tid))
            state.setdefault('superseded_threads', {})[tid] = {'by': newer[0]['key'], 'archived_at': int(time.time())}
            archived += 1
    return archived
