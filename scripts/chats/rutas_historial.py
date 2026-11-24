"""Reubica solo metadatos de una replica y recalcula offsets, sin editar mensajes."""
import bisect
import copy
import json
from pathlib import Path
from coverage_chats import normalize_windows_path


def relocate(raw, tables, source, destination):
    if str(source) == str(destination):
        return raw, tables
    starts, new_starts, changed, output = [], [], [], []
    old_size = new_size = 0
    for line in raw.splitlines(keepends=True):
        starts.append(old_size)
        new_starts.append(new_size)
        value = json.loads(line)
        payload = value.get('payload', {})
        replacement = line
        if value.get('type') in ('session_meta', 'turn_context') and isinstance(payload, dict):
            cwd = payload.get('cwd')
            if isinstance(cwd, str):
                try:
                    relative = Path(normalize_windows_path(cwd)).relative_to(Path(normalize_windows_path(str(source))))
                except ValueError:
                    pass
                else:
                    payload['cwd'] = str(Path(destination) / relative)
            # Only the execution metadata changes. Message contents and
            # permission rules remain intact; local policy still applies.
            if payload.get('cwd') != cwd:
                ending = b'\r\n' if line.endswith(b'\r\n') else b'\n'
                replacement = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8') + ending
        changed.append(replacement != line)
        output.append(replacement)
        old_size += len(line)
        new_size += len(replacement)
    starts.append(old_size)
    new_starts.append(new_size)

    def offset(value):
        if value is None:
            return None
        if not isinstance(value, int) or value < 0 or value > old_size:
            raise ValueError('Offset de historial fuera del rollout')
        index = bisect.bisect_right(starts, value) - 1
        remainder = value - starts[index]
        if remainder and changed[index]:
            raise ValueError('Offset dentro de metadatos reubicados; se conserva pendiente')
        return new_starts[index] + remainder

    result = copy.deepcopy(tables)
    fields = {'thread_turns': ('rollout_byte_offset', 'rollout_end_byte_offset'),
              'thread_history_projection_state': ('next_rollout_byte_offset',)}
    for table, names in fields.items():
        for row in result[table]:
            for name in names:
                if name in row:
                    row[name] = offset(row[name])
    return b''.join(output), result
