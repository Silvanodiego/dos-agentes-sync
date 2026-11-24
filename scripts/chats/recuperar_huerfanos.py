"""Preserva historiales SQLite sin rollout; no altera Codex ni inventa sesiones."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3


def exportar(backup, coverage, destination):
    inventory = json.loads(coverage.read_text(encoding='utf-8'))
    verified = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    if verified['status'] != 'verified':
        raise ValueError('Respaldo sin verificar')
    for name in ('state_5.sqlite', 'thread_history_1.sqlite'):
        expected = next(r['sha256'] for r in verified['files'] if r['path'] == name)
        with (backup / name).open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != expected:
                raise ValueError('Base modificada: ' + name)
    missing = {r['thread_id'] for r in inventory['missing']}
    destination.mkdir(parents=True, exist_ok=True)
    if (destination / 'indice.json').exists():
        raise ValueError('Ya existe el indice; no se duplica la recuperacion')
    result = []
    with closing(sqlite3.connect((backup / 'state_5.sqlite').resolve().as_uri() + '?mode=ro', uri=True)) as state, closing(sqlite3.connect((backup / 'thread_history_1.sqlite').resolve().as_uri() + '?mode=ro', uri=True)) as history:
        state.row_factory = history.row_factory = sqlite3.Row
        for row in state.execute("SELECT * FROM threads WHERE source IN ('vscode','cli','exec') AND preview<>'' AND attached_thread_parent_id IS NULL"):
            if row['id'] not in missing:
                continue
            # Only human threads, not guardian reviews or delegated subagents.
            if row['thread_source'] not in (None, 'user'):
                continue
            thread_id = row['id']
            if not all(c in '0123456789abcdef-' for c in thread_id.lower()):
                raise ValueError('ID no valido')
            tables = {}
            for table in ('thread_history_projection_state', 'thread_items', 'thread_turns', 'thread_realtime_items'):
                rows = [dict(r) for r in history.execute('SELECT * FROM ' + table + ' WHERE thread_id=?', (thread_id,))]
                tables[table] = rows
            items = sorted(tables['thread_items'], key=lambda i: (i['rollout_ordinal'], i['updated_at_ordinal'], i['item_id']))
            raw = {'original_thread': dict(row), 'tables': tables, 'native_resume_possible': False}
            raw_path = destination / (thread_id + '.json')
            with raw_path.open('x', encoding='utf-8') as f:
                json.dump(raw, f, ensure_ascii=False, indent=2)
            title = row['name'] or row['title'] or thread_id
            text_path = destination / (thread_id + '.txt')
            with text_path.open('x', encoding='utf-8') as f:
                f.write(f'{title}\nID original: {thread_id}\nHistorial recuperado de SQLite; no es una sesion reanudable.\n\n')
                for item in items:
                    f.write(f"\n--- ordinal {item['rollout_ordinal']} | {item['item_type']} | turno {item['turn_id']} ---\n")
                    try:
                        content = json.loads(item['item_json'])
                        f.write(json.dumps(content, ensure_ascii=False, indent=2) + '\n')
                    except (TypeError, json.JSONDecodeError):
                        f.write(str(item['item_json']) + '\n')
            result.append({'id': thread_id, 'title': title, 'cwd': row['cwd'],
                           'first_user_message': row['first_user_message'],
                           'items': len(items), 'turns': len(tables['thread_turns']),
                           'history_file': text_path.name, 'raw_file': raw_path.name,
                           'history_sha256': hashlib.sha256(text_path.read_bytes()).hexdigest(),
                           'raw_sha256': hashlib.sha256(raw_path.read_bytes()).hexdigest()})
    with (destination / 'indice.json').open('x', encoding='utf-8') as f:
        json.dump({'format': 1, 'chats': result}, f, ensure_ascii=False, indent=2)
    return {'exported': len(result), 'items': sum(r['items'] for r in result),
            'turns': sum(r['turns'] for r in result), 'destination': str(destination)}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backup', required=True, type=Path)
    p.add_argument('--coverage', required=True, type=Path)
    p.add_argument('--destination', required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(exportar(a.backup, a.coverage, a.destination)))
