"""Compatibilidad entre instalaciones; sin modificar perfiles reales."""
import base64
import copy
import json
from pathlib import Path
import tempfile

from test_sync_chats_abierto import LiveSyncTests, connection
import sync_chats_abierto as live
import proyectos_portables as projects


class StorageFormatsTests(LiveSyncTests):
    def legacy(self, home):
        (home / 'thread_history_1.sqlite').unlink()
        with connection(home / 'state_5.sqlite') as db:
            for column in ('history_mode', 'name', 'project_id', 'thread_section_id', 'thread_source'):
                db.execute('ALTER TABLE threads DROP COLUMN ' + column)

    def test_import_into_jsonl_index_without_creating_history_database(self):
        self.legacy(self.b)
        self.assertEqual(self.import_package(), 'imported')
        self.assertEqual(self.import_package(), 'already_imported')
        self.assertFalse(list(self.b.glob('thread_history*')))
        with connection(self.b / 'state_5.sqlite') as db:
            raw = Path(db.execute('SELECT rollout_path FROM threads').fetchone()[0]).read_bytes()
            self.assertIn(b'task_complete', raw)

    def test_legacy_export_and_active_turn_waits(self):
        self.legacy(self.a)
        raw = base64.b64decode(self.package['rollout'])
        path = Path(self.package['thread']['rollout_path'])
        path.write_bytes(raw + b'{"type":"event_msg","payload":{"type":"task_started"}}\n')
        with tempfile.TemporaryDirectory() as tmp:
            result = live.export_live(self.a, self.cloud, 'A', {}, Path(tmp))
        self.assertEqual(result['storage'], 'jsonl_index')
        self.assertEqual(result['generating_versions'], 1)
        manifest = json.loads((self.cloud / 'machines/A.json').read_bytes())
        package = live.read_object(self.cloud, manifest['chats'][0]['object'])
        self.assertTrue(package['busy'])
        self.assertTrue(all(not rows for rows in package['tables'].values()))

    def test_legacy_replica_does_not_echo_and_continuation_returns(self):
        self.legacy(self.b)
        self.import_package()
        state = {'import_baselines': self.baselines}
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(live.export_live(self.b, self.cloud, 'B', state, Path(tmp))['exported_chats'], 0)
        with connection(self.b / 'state_5.sqlite') as db:
            path = Path(db.execute('SELECT rollout_path FROM threads').fetchone()[0])
        with path.open('ab') as stream:
            stream.write(b'{"type":"event_msg","payload":{"type":"task_complete","text":"avance B"}}\n')
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(live.export_live(self.b, self.cloud, 'B', state, Path(tmp))['exported_chats'], 1)
        self.assertFalse(list(self.b.glob('thread_history*')))

    def test_destination_defaults_are_used_without_fabrication(self):
        with connection(self.b / 'state_5.sqlite') as db:
            db.execute("ALTER TABLE threads ADD COLUMN native_flag TEXT NOT NULL DEFAULT 'native'")
            db.execute('ALTER TABLE threads ADD COLUMN nullable_future TEXT')
        self.assertEqual(self.import_package(), 'imported')
        with connection(self.b / 'state_5.sqlite') as db:
            self.assertEqual(db.execute('SELECT native_flag,nullable_future FROM threads').fetchone(), ('native', None))

    def test_unknown_required_column_blocks_before_any_rollout(self):
        with connection(self.b / 'state_5.sqlite') as db:
            db.execute('ALTER TABLE threads ADD COLUMN required_future TEXT NOT NULL')
        with self.assertRaisesRegex(ValueError, 'required_future'):
            self.import_package()
        self.assertFalse(list(self.b.glob('sessions/**/*.jsonl')))

    def test_missing_history_with_unknown_mode_is_not_guessed(self):
        (self.b / 'thread_history_1.sqlite').unlink()
        with self.assertRaisesRegex(ValueError, 'history_mode'):
            self.import_package()
        self.assertFalse(list(self.b.glob('thread_history*')))

    def test_native_jsonl_default_is_respected(self):
        self.legacy(self.b)
        with connection(self.b / 'state_5.sqlite') as db:
            db.execute("ALTER TABLE threads ADD COLUMN history_mode TEXT NOT NULL DEFAULT 'jsonl'")
        self.assertEqual(self.import_package(), 'imported')
        with connection(self.b / 'state_5.sqlite') as db:
            self.assertEqual(db.execute('SELECT history_mode FROM threads').fetchone()[0], 'jsonl')
        self.assertFalse(list(self.b.glob('thread_history*')))

    def test_partial_history_is_not_announced_as_fully_synchronized(self):
        p = copy.deepcopy(self.package)
        p['rollout'] = None
        key = live.publish_package(self.cloud, p)
        live.atomic(self.cloud / 'machines/A.json', live.encoded({
            'format': live.FORMAT, 'machine': 'A', 'chats': [{'id': self.id, 'object': key}]}))
        result = live.sync_once(self.b, self.cloud, 'B', self.root / 'state.json', self.root)
        self.assertEqual(result['preserved_only'], 1)
        self.assertEqual(result['status'], 'partial_live')

    def test_legacy_projects_bind_cwd_without_native_project_api(self):
        roots = [projects.portable_path(self.root, self.b, self.cloud)]
        project = {'name': 'Proyecto', 'roots': roots, 'key': projects.project_key(roots)}
        state = {}
        def forbidden_rpc(*args):
            self.fail('Legacy Codex must not call project/create')
        registry = projects.ProjectRegistry(self.b, self.cloud, state, self.b / 'state_5.sqlite', rpc_factory=forbidden_rpc)
        self.assertIsNone(registry.resolve(project))
        self.assertEqual(state['project_bindings'][project['key']]['mode'], 'cwd_only')
        registry.close()

    def test_paginated_native_default_without_history_is_rejected(self):
        self.legacy(self.b)
        with connection(self.b / 'state_5.sqlite') as db:
            db.execute("ALTER TABLE threads ADD COLUMN history_mode TEXT NOT NULL DEFAULT 'paginated'")
        with self.assertRaisesRegex(ValueError, 'history_mode'):
            self.import_package()
        self.assertFalse(list(self.b.glob('thread_history*')))
