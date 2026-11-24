"""Pruebas de aislamiento, integridad y continuacion de replicas."""
import base64
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid

import sync_chats_abierto as live


@contextmanager
def connection(path):
    db = sqlite3.connect(path)
    try:
        with db:
            yield db
    finally:
        db.close()


class LiveSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.a, self.b, self.cloud = [self.root / p for p in ('a', 'b', 'cloud')]
        for home in (self.a, self.b):
            home.mkdir()
            with connection(home / 'state_5.sqlite') as db:
                db.execute('''CREATE TABLE threads(id TEXT PRIMARY KEY, rollout_path TEXT,
                  created_at INTEGER, source TEXT, thread_source TEXT, attached_thread_parent_id TEXT,
                  first_user_message TEXT, preview TEXT, title TEXT, name TEXT, cwd TEXT,
                  is_pinned INTEGER, project_id TEXT, thread_section_id TEXT, history_mode TEXT)''')
            with connection(home / 'thread_history_1.sqlite') as db:
                db.execute('CREATE TABLE thread_turns(thread_id TEXT, turn_id TEXT, status TEXT, rollout_ordinal INTEGER, PRIMARY KEY(thread_id,turn_id))')
                db.execute('CREATE TABLE thread_items(thread_id TEXT, item_id TEXT, item_json TEXT, PRIMARY KEY(thread_id,item_id))')
                db.execute('CREATE TABLE thread_realtime_items(thread_id TEXT, item_id TEXT)')
                db.execute('CREATE TABLE thread_history_projection_state(thread_id TEXT PRIMARY KEY, next_rollout_byte_offset INTEGER)')
        self.id = str(uuid.uuid4())
        rollout = self.a / 'sessions' / 'test.jsonl'
        rollout.parent.mkdir()
        raw = b'{ "type": "session_meta", "payload": {"id": "' + self.id.encode() + b'", "session_id": "' + self.id.encode() + b'"}}\r\n{"type":"event_msg","payload":{"type":"task_complete"}}\r\n'
        rollout.write_bytes(raw)
        thread = dict(id=self.id, rollout_path=str(rollout), created_at=1700000000,
                      source='vscode', thread_source='user', attached_thread_parent_id=None,
                      first_user_message='hola', preview='hola', title='Prueba', name=None,
                      cwd=str(self.root), is_pinned=1, project_id=None, thread_section_id=None,
                      history_mode='paginated')
        self.package = dict(format=live.FORMAT, machine='A', thread=thread,
                            rollout=base64.b64encode(raw).decode(), busy=False,
                            tables={t: [] for t in live.TABLES})
        self.package['tables']['thread_turns'] = [dict(thread_id=self.id, turn_id='turn', status='completed', rollout_ordinal=0)]
        self.package['tables']['thread_items'] = [dict(thread_id=self.id, item_id='item', item_json='{"text":"hola"}')]
        self.package['tables']['thread_history_projection_state'] = [dict(thread_id=self.id, next_rollout_byte_offset=len(raw))]
        with connection(self.a / 'state_5.sqlite') as db:
            live.insert_row(db, 'threads', thread)
        with connection(self.a / 'thread_history_1.sqlite') as db:
            for table, items in self.package['tables'].items():
                for item in items:
                    live.insert_row(db, table, item)
        self.ledger, self.baselines = set(), {}

    def import_package(self, package=None):
        package = package or self.package
        return live.import_version(self.b, package, live.digest(live.encoded(package)), self.ledger, self.root, self.baselines)

    def test_preserves_offsets_crlf_and_session_ids(self):
        original = base64.b64decode(self.package['rollout'])
        newid = str(uuid.uuid4())
        modified = live.validate_rollout(original, self.id, newid)
        self.assertEqual(len(original), len(modified))
        self.assertEqual(original.count(b'\r\n'), modified.count(b'\r\n'))
        self.assertNotIn(self.id.encode(), modified)
        self.assertEqual(modified.count(newid.encode()), 2)

    def test_idempotent_insert_and_original_preserved(self):
        self.assertEqual(self.import_package(), 'imported')
        self.assertEqual(self.import_package(), 'already_imported')
        with connection(self.b / 'state_5.sqlite') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM threads').fetchone()[0], 1)
        with connection(self.a / 'state_5.sqlite') as db:
            self.assertEqual(db.execute('SELECT id FROM threads').fetchone()[0], self.id)

    def test_incomplete_generation_waits(self):
        p = copy.deepcopy(self.package)
        p['busy'] = True
        self.assertEqual(self.import_package(p), 'preserved_only')
        self.assertFalse(self.ledger)

    def test_missing_rollout_is_archived_not_fabricated(self):
        p = copy.deepcopy(self.package)
        p['rollout'] = None
        self.assertEqual(self.import_package(p), 'preserved_only')
        self.assertFalse(self.ledger)

    def test_partial_line_rejected_before_visibility(self):
        p = copy.deepcopy(self.package)
        p['rollout'] = base64.b64encode(base64.b64decode(p['rollout']).rstrip()).decode()
        with self.assertRaises(ValueError):
            self.import_package(p)
        with connection(self.b / 'state_5.sqlite') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM threads').fetchone()[0], 0)

    def test_schema_mismatch_rejected(self):
        p = copy.deepcopy(self.package)
        p['tables']['thread_items'][0]['unknown_future_column'] = 'x'
        with self.assertRaises(ValueError):
            self.import_package(p)

    def test_corrupted_and_traversal_objects_rejected(self):
        key = live.publish_package(self.cloud, self.package)
        self.assertEqual(live.read_object(self.cloud, key), self.package)
        (self.cloud / 'objects' / (key + '.json.gz')).write_bytes(b'corrupt')
        with self.assertRaises(OSError):
            live.read_object(self.cloud, key)
        with self.assertRaises(ValueError):
            live.read_object(self.cloud, '../outside')

    def test_untouched_replica_does_not_echo_but_continuation_exports(self):
        self.import_package()
        state = {'import_baselines': self.baselines}
        with tempfile.TemporaryDirectory() as folder:
            result = live.export_live(self.b, self.cloud, 'B', state, Path(folder))
        self.assertEqual(result['exported_chats'], 0)
        with connection(self.b / 'thread_history_1.sqlite') as db:
            db.execute('UPDATE thread_items SET item_json=?', ('{"text":"continuacion local"}',))
        with tempfile.TemporaryDirectory() as folder:
            result = live.export_live(self.b, self.cloud, 'B', state, Path(folder))
        self.assertEqual(result['exported_chats'], 1)

    def test_cloud_manifest_import_with_app_databases_open(self):
        with tempfile.TemporaryDirectory() as folder:
            live.export_live(self.a, self.cloud, 'A', {}, Path(folder))
        with connection(self.b / 'state_5.sqlite') as opened:
            opened.execute('SELECT * FROM threads').fetchall()
            result = live.sync_once(self.b, self.cloud, 'B', self.root / 'state.json', self.root)
        self.assertEqual(result['imported_versions'], 1)
        self.assertEqual(result['exported_chats'], 0)
        again = live.sync_once(self.b, self.cloud, 'B', self.root / 'state.json', self.root)
        self.assertEqual(again['imported_versions'], 0)


if __name__ == '__main__':
    unittest.main()
