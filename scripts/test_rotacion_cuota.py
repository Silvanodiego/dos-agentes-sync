"""Regresiones sin cerrar procesos ni leer credenciales reales."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('quota_monitor', str(ROOT / 'monitor_cuota.pyw'))
spec = importlib.util.spec_from_loader(loader.name, loader)
monitor = importlib.util.module_from_spec(spec)
loader.exec_module(monitor)


class RotationTests(unittest.TestCase):
    def test_sqlite_wal_activity_prevents_false_idle(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            sessions = home / 'sessions'
            sessions.mkdir()
            wal = home / 'thread_history_1.sqlite-wal'
            wal.touch()
            os.utime(wal, (1000, 1000))
            with patch.object(monitor, 'SESSIONS', {1: sessions}), patch.object(monitor, 'session_files', return_value=[(100, sessions / 'old.jsonl')]):
                self.assertEqual(monitor.latest_write(), 1000)

    def test_block_survives_restart_and_corrupt_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(monitor, 'ROTATION_STATE', Path(temp) / 'state.json'):
            self.assertFalse(monitor.rotation_blocked())
            monitor.block_rotation('test')
            self.assertTrue(monitor.rotation_blocked())
            monitor.ROTATION_STATE.write_text('truncated')
            self.assertTrue(monitor.rotation_blocked())

    def test_failed_close_never_writes_live_auth_or_relaunches(self):
        with patch.object(monitor, 'desktop_target', return_value=('C:/app', 'app')), \
             patch.object(monitor, 'active_account', return_value=1), \
             patch.object(monitor, 'account_id', side_effect=lambda path: 'current' if path == monitor.LIVE_AUTH else 'destination'), \
             patch.object(monitor, 'atomic_copy') as copy, \
             patch.object(monitor.subprocess, 'run', return_value=Mock(returncode=1)), \
             patch.object(monitor.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(RuntimeError, 'pausada'):
                monitor.switch_account(1, 2)
            copy.assert_called_once_with(monitor.LIVE_AUTH, monitor.AUTHS[1])
            launch.assert_not_called()

    def test_failure_blocks_repeated_automatic_attempts(self):
        instance = monitor.Monitor.__new__(monitor.Monitor)
        instance.lock = threading.Lock()
        instance.switch_lock = threading.Lock()
        instance.switch_lock.acquire()
        instance.quota_wakeup = threading.Event()
        instance.notify = Mock()
        with tempfile.TemporaryDirectory() as temp, patch.object(monitor, 'ROTATION_STATE', Path(temp) / 'state.json'), \
             patch.object(monitor, 'switch_account', side_effect=RuntimeError('test')), \
             patch.object(monitor, 'active_account') as active:
            instance.perform_switch(1, 2, 'automatico')
            self.assertTrue(monitor.rotation_blocked())
            instance.check_automatic()
            instance.request_switch(reason='automatico')
            active.assert_not_called()
            self.assertFalse(instance.switch_lock.locked())
            instance.resume_automatic()
            self.assertFalse(monitor.rotation_blocked())

    def test_existing_chats_never_deleted(self):
        with patch.object(monitor, 'session_files') as files:
            monitor.cleanup_old_chats()
            files.assert_not_called()


if __name__ == '__main__':
    unittest.main()
