import json
from pathlib import Path
import tempfile
import sqlite3
import unittest
from unittest.mock import patch

import sync_chats_cerrado as sync
from limpiar_crashpad_huerfanos import eligible
import limpiar_crashpad_huerfanos as crashpad


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / 'home'
        self.home.mkdir()

    def save(self, name, content):
        path = self.root / name
        path.write_text(json.dumps(content), encoding='utf-8')
        return {'path': str(path), 'sha256': sync.sha256(path)}

    def recovery(self):
        history = self.save('history.txt', 'original')
        raw = self.save('raw.json', {'unchanged': True})
        index = self.save('indice.json', {'chats': [{'id': 'old', 'raw_file': 'raw.json',
            'raw_sha256': raw['sha256'], 'history_file': 'history.txt',
            'history_sha256': history['sha256']}]})
        mapping = self.save('mapping.json', {'chats': [{'original_id': 'old', 'threadId': 'new'}]})
        backup = self.save('backup.zip', 'verified backup')
        policy = self.save('acceptance.json', {'format': 1, 'known_missing': ['old', 'guardian'],
            'recovery_index': index, 'continuations': mapping, 'portable_backup': backup})
        sessions = self.home / 'sessions'
        sessions.mkdir()
        (sessions / 'rollout-new.jsonl').write_text('native', encoding='utf-8')
        return Path(policy['path'])

    def check(self, ids, acceptance):
        with patch.object(sync, 'coverage', return_value={'missing': [{'thread_id': i} for i in ids]}):
            sync.check_coverage(self.home, acceptance)

    def test_clean_closed_wal_database_inspected_without_source_writes(self):
        database = self.home / 'state_5.sqlite'
        connection = sqlite3.connect(database)
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('CREATE TABLE threads (id TEXT, rollout_path TEXT)')
        connection.execute("INSERT INTO threads VALUES ('old', 'sessions/missing.jsonl')")
        connection.commit()
        connection.close()
        before = {p.name: p.read_bytes() for p in self.home.iterdir()}
        self.assertEqual(sync.coverage(self.home)['missing'][0]['thread_id'], 'old')
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.home.iterdir()})

    def test_known_historical_gaps_require_verified_recovery(self):
        self.check(['old', 'guardian'], self.recovery())

    def test_future_gap_blocks(self):
        policy = self.recovery()
        with self.assertRaisesRegex(ValueError, 'NUEVAS'):
            self.check(['old', 'future'], policy)

    def test_modified_history_blocks(self):
        policy = self.recovery()
        (self.root / 'history.txt').write_text('altered', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'alterado'):
            self.check(['old'], policy)

    def test_missing_native_continuation_blocks(self):
        policy = self.recovery()
        (self.home / 'sessions' / 'rollout-new.jsonl').unlink()
        with self.assertRaisesRegex(ValueError, 'rollout nativo'):
            self.check(['old'], policy)

    def test_archived_compressed_continuation_accepted(self):
        policy = self.recovery()
        archived = self.home / 'archived_sessions'
        archived.mkdir()
        (self.home / 'sessions' / 'rollout-new.jsonl').rename(archived / 'rollout-new.jsonl.zst')
        self.check(['old'], policy)

    def test_no_recovery_required_without_gaps(self):
        self.check([], None)

    def test_no_implicit_discard_of_missing_history(self):
        with self.assertRaisesRegex(ValueError, 'sin recuperacion'):
            self.check(['old'], None)

    def test_core_receives_no_close_and_no_conflict_overwrite(self):
        with patch.object(sync, 'validate_config', return_value=self.home), \
             patch.object(sync, 'check_coverage'), patch.object(sync, 'cleanup', return_value=[]), \
             patch.object(sync.subprocess, 'run') as run:
            run.return_value.returncode = 3
            result = sync.execute(self.root, None, Path('python.exe'))
            command = run.call_args.args[0]
            self.assertIn('--unattended', command)
            self.assertEqual(command[-1], 'manual_abort')
            self.assertEqual(result['status'], 'waiting_codex_closed')

    def test_coverage_failure_never_starts_core(self):
        with patch.object(sync, 'validate_config', return_value=self.home), \
             patch.object(sync, 'check_coverage', side_effect=ValueError('gap')), \
             patch.object(sync.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                sync.execute(self.root, None, Path('python.exe'))
            run.assert_not_called()


class CrashpadTests(unittest.TestCase):
    def record(self, pid, parent, kind='crashpad-handler', born=10, path=None):
        return {'pid': pid, 'parent': parent, 'kind': kind, 'born': born,
                'path': path or r'C:\Program Files\WindowsApps\OpenAI.Codex_26.1_x64__package\app\ChatGPT.exe'}

    def test_only_orphan_handler_chain_selected(self):
        rows = [self.record(1, 99), self.record(2, 1, born=11)]
        self.assertEqual({p['pid'] for p in eligible(rows, r'C:\Program Files')}, {1, 2})

    def test_active_application_tree_preserved(self):
        rows = [self.record(1, 99, kind=''), self.record(2, 1, born=11)]
        self.assertEqual(eligible(rows, r'C:\Program Files'), [])

    def test_pid_reuse_preserved(self):
        rows = [self.record(1, 99, born=20), self.record(2, 1, born=10)]
        self.assertEqual(eligible(rows, r'C:\Program Files'), [])

    def test_other_chatgpt_package_preserved(self):
        rows = [self.record(1, 99, path=r'C:\Program Files\WindowsApps\OpenAI.ChatGPT_x\app\ChatGPT.exe')]
        self.assertEqual(eligible(rows, r'C:\Program Files'), [])

    def test_mixed_orphan_tree_preserved(self):
        rows = [self.record(1, 99), self.record(2, 1, kind='utility')]
        self.assertEqual(eligible(rows, r'C:\Program Files'), [])

    def test_cycle_preserved(self):
        rows = [self.record(1, 2), self.record(2, 1)]
        self.assertEqual(eligible(rows, r'C:\Program Files'), [])

    def node(self):
        return dict(self.record(7, 99, kind='utility'), subtype='node.mojom.NodeService')

    def test_orphan_node_selected_only_without_active_codex(self):
        self.assertEqual([p['pid'] for p in eligible([self.node()], r'C:\Program Files')], [7])
        self.assertEqual(eligible([self.node(), self.record(8, 99, kind='')], r'C:\Program Files'), [])

    def test_node_with_child_or_unknown_type_preserved(self):
        self.assertEqual(eligible([self.node(), self.record(8, 7, kind='')], r'C:\Program Files'), [])
        node = self.node()
        node['subtype'] = 'unknown'
        self.assertEqual(eligible([node], r'C:\Program Files'), [])

    def test_unknown_codex_executable_blocks_node_cleanup(self):
        other = dict(self.record(8, 99, kind=''), name='codex.exe', path=None)
        self.assertEqual(eligible([self.node(), other], r'C:\Program Files'), [])

    def test_first_observation_and_grace_never_terminate(self):
        rows = [self.record(1, 99)]
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(crashpad, 'snapshot', return_value=rows), \
             patch.object(crashpad.time, 'time', side_effect=[100.0, 150.0]), \
             patch.dict(crashpad.os.environ, {'ProgramFiles': r'C:\Program Files'}), \
             patch.object(crashpad.ctypes, 'WinDLL') as kernel:
            self.assertEqual(crashpad.cleanup(Path(directory)), [])
            self.assertEqual(crashpad.cleanup(Path(directory)), [])
            kernel.assert_not_called()


if __name__ == '__main__':
    unittest.main()
