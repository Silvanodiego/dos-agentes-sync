"""Regresiones sin instalar, autenticar ni registrar tareas del equipo real."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

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
            result = activation.activate(Path(temp), Path(temp) / 'activation.json', runner=run)
            self.assertEqual(result['status'], 'activated')
            self.assertEqual(len(calls), 2)
            self.assertIn('CodexChatsAutoSetup', calls[1][-1])
            self.assertNotIn('CodexChatsSyncLive', calls[1][-1])

    def test_timeout_is_pending_and_keeps_retry_available(self):
        with tempfile.TemporaryDirectory() as temp:
            def run(command, **options):
                raise subprocess.TimeoutExpired(command, 100)
            result = activation.activate(Path(temp), Path(temp) / 'activation.json', runner=run)
            self.assertEqual(result['status'], 'pending')


if __name__ == '__main__':
    unittest.main()
