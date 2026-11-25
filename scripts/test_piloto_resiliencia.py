"""Pruebas aisladas: no Codex real, CDP ni consultas a modelos."""
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import piloto_gemini as p


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / 'piloto.log'

    def test_inactivity_kills_tree(self):
        process = Mock()
        process.communicate.side_effect = subprocess.TimeoutExpired('codex', 1)
        with patch.object(p.shutil, 'which', return_value='codex.exe'), \
             patch.object(p.subprocess, 'Popen', return_value=process), \
             patch.object(p.time, 'monotonic', side_effect=[0, 0, 301]), \
             patch.object(p, 'stop_process') as stop:
            with self.assertRaisesRegex(p.TransientFailure, 'INACTIVIDAD'):
                p.codex_step(self.root, 'task', self.root / 'out.txt', 900)
        stop.assert_called_once_with(process)
        self.assertIn('INACTIVIDAD 300 s', self.log.read_text(encoding='utf-8'))

    def test_output_activity_resets_idle_clock(self):
        process = Mock(returncode=0)
        output = self.root / 'out.txt'
        def communicate(*args, **kwargs):
            if process.communicate.call_count < 3:
                raise subprocess.TimeoutExpired('codex', 1)
            output.write_text('done', encoding='utf-8')
        process.communicate.side_effect = communicate
        with patch.object(p.shutil, 'which', return_value='codex.exe'), \
             patch.object(p.subprocess, 'Popen', return_value=process), \
             patch.object(p.time, 'monotonic', side_effect=[0, 0, 299, 301, 598, 599]), \
             patch.object(p, 'activity_signature', side_effect=[(0,), (1,), (2,)]):
            self.assertEqual(p.codex_step(self.root, 'task', output, 900), 'done')

    def test_total_timeout_is_capped_at_900(self):
        process = Mock()
        with patch.object(p.shutil, 'which', return_value='codex.exe'), \
             patch.object(p.subprocess, 'Popen', return_value=process), \
             patch.object(p.time, 'monotonic', side_effect=[0, 901]), \
             patch.object(p, 'stop_process') as stop:
            with self.assertRaisesRegex(p.TransientFailure, "TIMEOUT total"):
                p.codex_step(self.root, 'task', self.root / 'out.txt', 5000)
        stop.assert_called_once()

    def test_success_after_one_transient_failure(self):
        operation = Mock(side_effect=[ConnectionError('offline'), 'OK'])
        with patch.object(p, 'recover_services') as recover, patch.object(p.time, 'sleep') as sleep:
            self.assertEqual(p.with_retry(operation, 'CODEX', self.log), 'OK')
        self.assertEqual(operation.call_count, 2)
        recover.assert_called_once_with(self.log)
        sleep.assert_called_once_with(10)

    def test_retry_is_limited_to_one(self):
        operation = Mock(side_effect=TimeoutError('timeout'))
        with patch.object(p, 'recover_services') as recover, patch.object(p.time, 'sleep'):
            with self.assertRaises(TimeoutError):
                p.with_retry(operation, 'GEMINI', self.log)
        self.assertEqual(operation.call_count, 2)
        recover.assert_called_once()

    def test_empty_response_is_retried(self):
        operation = Mock(side_effect=[' ', 'OK'])
        with patch.object(p, 'recover_services'), patch.object(p.time, 'sleep'):
            self.assertEqual(p.with_retry(operation, 'GEMINI', self.log), 'OK')
        self.assertEqual(operation.call_count, 2)

    def test_final_delivery_is_not_retried(self):
        operation = Mock(return_value='[ENTREGA_FINAL]\nListo')
        with patch.object(p, 'recover_services') as recover, patch.object(p.time, 'sleep') as sleep:
            self.assertTrue(p.delivery_complete(p.with_retry(operation, 'GEMINI', self.log)))
        operation.assert_called_once_with(0)
        recover.assert_not_called()
        sleep.assert_not_called()

    def test_authentication_is_not_retried(self):
        for message in ('401 unauthorized', 'Falta iniciar sesión de Google',
                        'Invalid credentials; timeout', 'Authentication failed'):
            with self.subTest(message=message):
                operation = Mock(side_effect=p.ChatFijoError(message))
                with patch.object(p, 'recover_services') as recover, patch.object(p.time, 'sleep') as sleep:
                    with self.assertRaises(p.ChatFijoError):
                        p.with_retry(operation, 'GEMINI', self.log)
                operation.assert_called_once_with(0)
                recover.assert_not_called()
                sleep.assert_not_called()

    def test_codex_credentials_in_log_are_not_retried(self):
        process = Mock(returncode=1)
        output = self.root / 'out.txt'
        process.communicate.side_effect = lambda *a, **k: output.with_suffix('.log').write_text(
            '401 authentication failed', encoding='utf-8')
        with patch.object(p.shutil, 'which', return_value='codex.exe'), \
             patch.object(p.subprocess, 'Popen', return_value=process):
            with self.assertRaises(p.AuthenticationFailure):
                p.codex_step(self.root, 'task', output, 900)

    def test_gemini_retry_reads_pending_response_without_resending(self):
        chat = Mock()
        chat.__enter__ = Mock(return_value=chat)
        chat.__exit__ = Mock(return_value=False)
        chat.message_sent = True
        chat.config = Mock()
        chat.creating = False
        chat.ask.side_effect = TimeoutError('timeout')
        chat.page.evaluate.return_value = {'key': 'new', 'text': '[ENTREGA_FINAL]'}
        tracker = Mock()
        tracker.observe.return_value = '[ENTREGA_FINAL]'
        with patch.object(p, 'GeminiChat', return_value=chat), \
             patch.object(p, 'ResponseTracker', return_value=tracker), \
             patch.object(p, 'recover_services') as recover, patch.object(p.time, 'sleep'):
            answer = p.gemini_step(Mock(), 'review', 180, self.log)
        self.assertEqual(answer, '[ENTREGA_FINAL]')
        chat.ask.assert_called_once()
        recover.assert_called_once()


if __name__ == '__main__':
    unittest.main()
