"""Catalogo portable de proyectos; no copia configuracion global ni credenciales."""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import sqlite3
import subprocess
import threading
import time


def normalized(path):
    return os.path.normcase(os.path.normpath(str(path)))


def drive_root(cloud):
    # CloudRoot is <Drive>/CodexSync/live-v1 on all PCs; drive letters may differ.
    if cloud.parent.name.casefold() == 'codexsync':
        return cloud.parent.parent
    return None


def portable_path(path, home, cloud):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Ruta de proyecto no absoluta')
    anchors = [('drive', drive_root(cloud)), ('profile', home.parent)]
    for kind, root in anchors:
        if root is not None:
            try:
                return {'anchor': kind, 'path': path.relative_to(root).as_posix()}
            except ValueError:
                pass
    return {'anchor': 'absolute', 'path': str(path)}


def local_path(record, home, cloud, mappings=None):
    kind, value = record['anchor'], record['path']
    if kind in ('drive', 'profile'):
        root = drive_root(cloud) if kind == 'drive' else home.parent
        relative = Path(value)
        if root is None or relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Ruta portable fuera del ancla autorizada')
        result = root / relative
        if not result.resolve().is_relative_to(root.resolve()):
            raise ValueError('Ruta enlazada fuera del ancla autorizada')
        return result
    if kind != 'absolute' or not Path(value).is_absolute():
        raise ValueError('Ancla de proyecto desconocida')
    # Explicit prefix mappings take precedence over equal absolute paths.
    for source, target in sorted((mappings or {}).items(), key=lambda p: -len(p[0])):
        try:
            return Path(target) / Path(value).relative_to(Path(source))
        except ValueError:
            pass
    return Path(value)


def project_key(roots):
    data = json.dumps(roots, sort_keys=True, ensure_ascii=False).casefold().encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def catalog(home, cloud, db):
    """Merge native projects and the allowlisted legacy sidebar associations."""
    native = {}
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='projects'").fetchone():
        for row in db.execute('SELECT id,name FROM projects ORDER BY position'):
            roots = [r[0] for r in db.execute('SELECT path FROM project_roots WHERE project_id=? ORDER BY position', (row[0],))]
            native[row[0]] = {'name': row[1], 'roots': roots}
    legacy = {}
    assignments = {}
    global_file = home / '.codex-global-state.json'
    if global_file.is_file() and not global_file.is_symlink():
        raw = json.loads(global_file.read_text(encoding='utf-8'))
        for key, value in raw.get('local-projects', {}).items():
            if isinstance(value, dict) and value.get('rootPaths'):
                legacy[key] = {'name': value['name'], 'roots': value['rootPaths']}
        assignments = {tid: value['projectId'] for tid, value in raw.get('thread-project-assignments', {}).items()
                       if isinstance(value, dict) and value.get('projectKind') == 'local' and value.get('projectId') in legacy}
    projects, lookup = {}, {}
    for pid, value in list(native.items()) + list(legacy.items()):
        roots = [portable_path(path, home, cloud) for path in value['roots']]
        key = project_key(roots)
        projects.setdefault(key, {'key': key, 'name': value['name'], 'roots': roots})
        lookup[pid] = projects[key]
    return list(projects.values()), lookup, assignments


def project_for(thread, lookup, assignments, home, cloud):
    explicit = lookup.get(thread.get('project_id')) or lookup.get(assignments.get(thread['id']))
    if explicit:
        return explicit
    # Legacy chats can predate project_id. Infer only an unambiguous longest root.
    matches = []
    cwd = Path(thread['cwd'])
    for project in {p['key']: p for p in lookup.values()}.values():
        for record in project['roots']:
            root = local_path(record, home, cloud)
            if cwd.is_relative_to(root):
                matches.append((len(root.parts), project))
    if not matches:
        return None
    matches.sort(key=lambda pair: pair[0], reverse=True)
    best = [project for depth, project in matches if depth == matches[0][0]]
    return best[0] if len({p['key'] for p in best}) == 1 else None


class AppServer:
    """Own short-lived metadata client. Never starts/resumes turns or inference."""
    def __init__(self, home, executable=None):
        if executable is None:
            base = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'WindowsApps'
            candidates = list(base.glob('OpenAI.Codex_*/app/resources/codex.exe'))
            executable = str(max(candidates, key=lambda p: p.stat().st_mtime)) if candidates else shutil.which('codex')
        if not executable:
            raise OSError('No se encuentra el binario nativo de Codex')
        self.process = subprocess.Popen([str(executable), 'app-server'],
            env=dict(os.environ, CODEX_HOME=str(home)), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.messages = queue.Queue()
        self.sequence = 0
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.call('initialize', {'clientInfo': {'name': 'project_sync', 'version': '2'},
                                   'capabilities': {'experimentalApi': True}})
            self.process.stdin.write(b'{"method":"initialized","params":{}}\n')
            self.process.stdin.flush()
        except Exception:
            self.close()
            raise

    def _read(self):
        for line in self.process.stdout:
            try:
                self.messages.put(json.loads(line))
            except ValueError:
                pass
        self.messages.put({'closed': True})

    def call(self, method, params):
        self.sequence += 1
        self.process.stdin.write((json.dumps({'id': self.sequence, 'method': method, 'params': params}) + '\n').encode())
        self.process.stdin.flush()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                message = self.messages.get(timeout=max(.01, deadline - time.monotonic()))
            except queue.Empty:
                break
            if message.get('closed'):
                raise OSError('El app-server de metadatos termino inesperadamente')
            if message.get('id') == self.sequence:
                if 'error' in message:
                    raise ValueError(str(message['error']))
                return message['result']
        raise TimeoutError('Tiempo agotado en ' + method)

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()  # Only the helper process created above.
        self.process.wait(timeout=10)
        self.process.stdin.close()
        self.process.stdout.close()


class ProjectRegistry:
    def __init__(self, home, cloud, state, state_db, mappings=None, rpc_factory=AppServer):
        self.home, self.cloud, self.state = home, cloud, state
        self.mappings, self.factory, self.rpc = mappings or {}, rpc_factory, None
        self.projects = state.setdefault('project_bindings', {})
        self.existing = {}
        with closing(sqlite3.connect(state_db)) as db:
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='projects'").fetchone():
                for pid, in db.execute('SELECT id FROM projects'):
                    roots = tuple(normalized(r[0]) for r in db.execute('SELECT path FROM project_roots WHERE project_id=? ORDER BY position', (pid,)))
                    self.existing[roots] = pid

    def resolve(self, project):
        roots = [local_path(r, self.home, self.cloud, self.mappings) for r in project['roots']]
        if not roots or any(not p.is_dir() for p in roots):
            raise ValueError('Carpeta de proyecto pendiente de Drive/mapeo: ' + project['name'])
        signature = tuple(normalized(path) for path in roots)
        pid = self.existing.get(signature)
        if pid is None:
            if self.rpc is None:
                self.rpc = self.factory(self.home)
            response = self.rpc.call('project/create', {
                'idempotencyKey': 'codexsync-' + project['key'], 'name': project['name'],
                'roots': [{'path': str(path)} for path in roots],
                'metadata': {'codexsync_key': project['key']}})
            pid = response['project']['id']
            self.existing[signature] = pid
        self.projects[project['key']] = {'id': pid, 'roots': [str(p) for p in roots], 'name': project['name']}
        return pid

    def close(self):
        if self.rpc is not None:
            self.rpc.close()
