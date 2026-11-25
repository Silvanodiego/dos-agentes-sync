"""Regresiones sin instalar, autenticar ni registrar tareas del equipo real."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

from verificar_npm_instalado import installed
from verificar_token_saver import source_version

spec = importlib.util.spec_from_file_location('activation', Path(__file__).parent / 'chats/activar_cuando_listo.py')
activation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activation)


class ReinstallTests(unittest.TestCase):
    def test_lock_versions_and_missing_dependency(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lock = {'packages': {'': {}, 'node_modules/a': {'version': '1.2.3'},
                                  'node_modules/optional': {'version': '2.0.0', 'optional': True}}}
            (root / 'package-lock.json').write_text(json.dumps(lock))
            self.assertFalse(installed(root))
            manifest = root / 'node_modules/a/package.json'
            manifest.parent.mkdir(parents=True)
            manifest.write_text('{"version":"1.2.3"}')
            self.assertTrue(installed(root))
            manifest.write_text('{"version":"1.2.2"}')
            self.assertFalse(installed(root))
            manifest.write_text('truncated')
            self.assertFalse(installed(root))

    def test_token_saver_version_without_import(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'src').mkdir()
            (root / 'src/__init__.py').write_text('__version__ = "3.0.1"\nraise RuntimeError("No ejecutar")')
            self.assertEqual(source_version(root), '3.0.1')

    def test_chat_waits_without_claiming_activation(self):
        with tempfile.TemporaryDirectory() as temp:
            calls = []
            def run(command, **options):
                calls.append(command)
                return subprocess.CompletedProcess(command, 1, '', 'Falta Drive o base nativa')
            status = Path(temp) / 'activation.json'
            result = activation.activate(Path(temp), status, runner=run)
            self.assertEqual(result['status'], 'pending')
            self.assertEqual(len(calls), 1)
            self.assertEqual(json.loads(status.read_text())['status'], 'pending')

    def test_chat_activation_disables_only_bootstrap(self):
        with tempfile.TemporaryDirectory() as temp:
            calls = []
            def run(command, **options):
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, 'Activa', '')
            result = activation.activate(Path(temp), Path(temp) / 'activation.json', runner=run,
                                         verifier=lambda *args: (True, 'sync verificada'))
            self.assertEqual(result['status'], 'activated')
            self.assertEqual(len(calls), 2)
            self.assertIn('CodexChatsAutoSetup', calls[1][-1])
            self.assertNotIn('CodexChatsSyncLive', calls[1][-1])

    def test_registered_task_without_success_keeps_bootstrap(self):
        with tempfile.TemporaryDirectory() as temp:
            calls = []
            def run(command, **options):
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, 'Tarea registrada', '')
            result = activation.activate(Path(temp), Path(temp) / 'activation.json', runner=run,
                                         verifier=lambda *args: (False, 'Worker bloqueado'))
            self.assertEqual(result['status'], 'pending')
            self.assertEqual(len(calls), 1)
            self.assertIn('Worker bloqueado', result['detail'])

    def test_first_sync_requires_fresh_success_not_stale_or_blocked_status(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'live-sync-status.json'
            started = datetime.now(timezone.utc)
            for status, checked, expected in (
                ('synchronized_live', started - timedelta(minutes=1), False),
                ('blocked', started + timedelta(seconds=1), False),
                ('partial_live', started + timedelta(seconds=1), False),
                ('synchronized_live', started + timedelta(seconds=1), True),
            ):
                path.write_text(json.dumps({'status': status, 'checked_at_utc': checked.isoformat()}))
                self.assertEqual(activation.wait_for_sync(path, started, timeout=0)[0], expected)

    def test_timeout_is_pending_and_keeps_retry_available(self):
        with tempfile.TemporaryDirectory() as temp:
            def run(command, **options):
                raise subprocess.TimeoutExpired(command, 100)
            result = activation.activate(Path(temp), Path(temp) / 'activation.json', runner=run)
            self.assertEqual(result['status'], 'pending')


if __name__ == '__main__':
    unittest.main()
