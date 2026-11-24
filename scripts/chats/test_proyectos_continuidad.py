"""Pruebas entre perfiles independientes, proyectos futuros y ramas concurrentes."""
import base64
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile

from test_sync_chats_abierto import LiveSyncTests, connection
import sync_chats_abierto as live
import proyectos_portables as projects


class ProjectsAndContinuityTests(LiveSyncTests):
    def setUp(self):
        super().setUp()
        for home in (self.a, self.b):
            with connection(home / 'state_5.sqlite') as db:
                db.execute('ALTER TABLE threads ADD COLUMN archived INTEGER NOT NULL DEFAULT 0')
                db.execute('ALTER TABLE threads ADD COLUMN archived_at INTEGER')
                db.execute('CREATE TABLE projects(id TEXT PRIMARY KEY,name TEXT,position INTEGER)')
                db.execute('CREATE TABLE project_roots(project_id TEXT,position INTEGER,path TEXT)')
        self.package['thread'].update(archived=0, archived_at=None)

    def cycle(self, home, machine):
        return live.sync_once(home, self.cloud, machine, self.root / (machine + '.json'), self.root)

    def append(self, home, tid, label):
        with connection(home / 'state_5.sqlite') as db:
            path = Path(db.execute('SELECT rollout_path FROM threads WHERE id=?', (tid,)).fetchone()[0])
        with path.open('ab') as stream:
            stream.write((json.dumps({'type': 'event_msg', 'payload': {'type': 'task_complete', 'text': label}}) + '\n').encode())
        with connection(home / 'thread_history_1.sqlite') as db:
            db.execute('INSERT INTO thread_items VALUES(?,?,?)', (tid, label, json.dumps({'text': label})))

    def visible(self, home):
        with connection(home / 'state_5.sqlite') as db:
            return [r[0] for r in db.execute('SELECT id FROM threads WHERE archived=0')]

    def test_new_versions_archive_old_replicas_without_deleting_history(self):
        self.cycle(self.a, 'A')
        self.cycle(self.b, 'B')
        first = self.visible(self.b)[0]
        self.append(self.a, self.id, 'avance-A')
        self.cycle(self.a, 'A')
        result = self.cycle(self.b, 'B')
        self.assertEqual(result['archived_predecessors'], 1)
        self.assertNotIn(first, self.visible(self.b))
        self.assertEqual(len(self.visible(self.b)), 1)
        with connection(self.b / 'thread_history_1.sqlite') as db:
            self.assertGreater(db.execute('SELECT count(*) FROM thread_items WHERE thread_id=?', (first,)).fetchone()[0], 0)

    def test_continuation_returns_to_original_pc_as_same_logical_chat(self):
        self.cycle(self.a, 'A')
        self.cycle(self.b, 'B')
        replica = self.visible(self.b)[0]
        self.append(self.b, replica, 'avance-B')
        self.cycle(self.b, 'B')
        result = self.cycle(self.a, 'A')
        self.assertEqual(result['archived_predecessors'], 1)
        self.assertEqual(len(self.visible(self.a)), 1)
        self.assertNotIn(self.id, self.visible(self.a))
        state = json.loads((self.root / 'A.json').read_bytes())
        self.assertEqual(state['replica_lineage'][self.visible(self.a)[0]]['logical_id'], 'A:' + self.id)

    def test_parallel_offline_edits_keep_both_branches(self):
        self.cycle(self.a, 'A')
        self.cycle(self.b, 'B')
        self.append(self.a, self.id, 'avance-A-offline')
        self.append(self.b, self.visible(self.b)[0], 'avance-B-offline')
        self.cycle(self.b, 'B')
        self.cycle(self.a, 'A')
        self.assertEqual(len(self.visible(self.a)), 2)
        self.assertIn(self.id, self.visible(self.a))

    def test_active_generation_not_archived(self):
        self.cycle(self.a, 'A')
        self.cycle(self.b, 'B')
        self.append(self.b, self.visible(self.b)[0], 'avance-B')
        self.cycle(self.b, 'B')
        with connection(self.a / 'thread_history_1.sqlite') as db:
            db.execute("UPDATE thread_turns SET status='in_progress' WHERE thread_id=?", (self.id,))
        self.cycle(self.a, 'A')
        self.assertIn(self.id, self.visible(self.a))

    def test_new_project_detected_without_chats_and_no_global_secrets(self):
        (self.a / '.codex-global-state.json').write_text(json.dumps({
            'local-projects': {'legacy': {'name': 'Proyecto futuro', 'rootPaths': [str(self.root)]}},
            'thread-project-assignments': {self.id: {'projectKind': 'local', 'projectId': 'legacy'}},
            'secret': 'DO_NOT_EXPORT', 'auth': {'token': 'DO_NOT_EXPORT'}}), encoding='utf-8')
        self.cycle(self.a, 'A')
        manifest = json.loads((self.cloud / 'machines/A.json').read_bytes())
        self.assertEqual(len(manifest['projects']), 1)
        package = live.read_object(self.cloud, manifest['chats'][0]['object'])
        self.assertEqual(package['project']['name'], 'Proyecto futuro')
        self.assertNotIn('DO_NOT_EXPORT', json.dumps(manifest) + json.dumps(package))
        (self.a / '.codex-global-state.json').write_text(json.dumps({'local-projects': {
            'legacy': {'name': 'Proyecto futuro', 'rootPaths': [str(self.root)]},
            'new': {'name': 'Otro proyecto', 'rootPaths': [str(self.a)]}}}), encoding='utf-8')
        self.cycle(self.a, 'A')
        self.assertEqual(len(json.loads((self.cloud / 'machines/A.json').read_bytes())['projects']), 2)

    def test_drive_mapping_and_project_local_id(self):
        drive_a, drive_b = self.root / 'driveA', self.root / 'driveB'
        cloud_a, cloud_b = drive_a / 'CodexSync/live-v1', drive_b / 'CodexSync/live-v1'
        source, destination = drive_a / 'Claude/proyecto', drive_b / 'Claude/proyecto'
        source.mkdir(parents=True)
        destination.mkdir(parents=True)
        roots = [projects.portable_path(source, self.a, cloud_a)]
        project = {'name': 'proyecto', 'key': projects.project_key(roots), 'roots': roots}
        with connection(self.b / 'state_5.sqlite') as db:
            db.execute('INSERT INTO projects VALUES(?,?,0)', ('local-project-B', 'proyecto'))
            db.execute('INSERT INTO project_roots VALUES(?,0,?)', ('local-project-B', str(destination)))
        state = {}
        registry = projects.ProjectRegistry(self.b, cloud_b, state, self.b / 'state_5.sqlite')
        self.package.update(project=project, workspace=roots[0])
        status = live.import_version(self.b, self.package, live.digest(live.encoded(self.package)), self.ledger, self.root, self.baselines, registry)
        self.assertEqual(status, 'imported')
        with connection(self.b / 'state_5.sqlite') as db:
            self.assertEqual(db.execute('SELECT project_id,cwd FROM threads').fetchone(), ('local-project-B', str(destination)))

    def test_missing_folder_and_traversal_never_fall_back_to_unrelated_project(self):
        self.package['thread']['cwd'] = str(self.root / 'missing')
        with self.assertRaisesRegex(ValueError, 'ausente'):
            self.import_package()
        for value in ('../escape', '/absolute'):
            with self.assertRaises(ValueError):
                projects.local_path({'anchor': 'profile', 'path': value}, self.a, self.cloud)
        self.assertEqual(self.visible(self.b), [])

    def test_native_relocation_is_idempotent(self):
        self.import_package()
        with connection(self.b / 'state_5.sqlite') as db:
            tid, old = db.execute('SELECT id,rollout_path FROM threads').fetchone()
            new = self.b / 'sessions' / 'relocated.jsonl'
            Path(old).rename(new)
            db.execute('UPDATE threads SET rollout_path=? WHERE id=?', (str(new), tid))
        self.assertEqual(self.import_package(), 'already_imported')

    def test_windows_extended_prefix_has_same_portable_identity(self):
        drive = self.root / 'drive'
        cloud = drive / 'CodexSync/live-v1'
        folder = drive / 'Claude/proyecto'
        ordinary = projects.portable_path(folder, self.a, cloud)
        extended = projects.portable_path('\\\\?\\' + str(folder), self.a, cloud)
        self.assertEqual(ordinary, extended)

    def test_invalid_lineage_is_rejected_before_chat_becomes_visible(self):
        self.package['lineage'] = {'logical_id': 'A:test', 'ancestors': ['not-a-hash']}
        with self.assertRaisesRegex(ValueError, 'Ascendencia'):
            self.import_package()
        self.assertEqual(self.visible(self.b), [])


if __name__ == '__main__':
    import unittest
    unittest.main()
