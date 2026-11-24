"""Pruebas de regresión: fallos, cooldown, notificaciones y controles HTTP."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import urllib.request
import urllib.error
import monitor_services as services
import panel_control as panel
from tray_monitor import Monitor

class MonitorTests(unittest.TestCase):
    def test_cascada_requires_both_services(self):
        def request(port, path):
            if port == 8045:
                raise OSError('cerrado')
            return {'status': 'ready'}
        with patch.object(services, 'http_json', side_effect=request):
            result = services.cascada_status()
        self.assertFalse(result['ok'])
        self.assertIn('8045', result['detail'])
        self.assertTrue(result['services']['8765']['ok'])

    def test_google_redirect_requires_manual_login(self):
        def request(port, path):
            if path == '/json/version':
                return {'webSocketDebuggerUrl': 'ws://localhost'}
            return [{'type': 'page', 'url': 'https://accounts.google.com/ServiceLogin'}, {'type': 'page', 'url': 'https://gemini.google.com/app/abc'}]
        with patch.object(services, 'http_json', side_effect=request), patch.object(services, 'projects', return_value=[]):
            result = services.chat_status()
        self.assertTrue(result['cdp'])
        self.assertTrue(result['login_required'])
        self.assertFalse(result['ok'])

    def test_watchdog_cooldown_is_per_service(self):
        m = Monitor.__new__(Monitor)
        m.last, m.icon, m.stop = {}, Mock(), Mock()
        with patch('tray_monitor.time.monotonic', side_effect=[1000, 1015, 1016, 1300]), patch.object(services, 'action') as action, patch.object(services, 'start_panel') as start:
            self.assertTrue(m.recover('9222'))
            self.assertFalse(m.recover('9222'))
            self.assertTrue(m.recover('8787'))
            self.assertTrue(m.recover('9222'))
        self.assertEqual(action.call_count, 2)
        start.assert_called_once()

    def test_one_notification_per_incident_then_reset(self):
        m = Monitor.__new__(Monitor)
        m.icon, m.notified = Mock(), set()
        good = {'ok': True, 'detail': 'OK', 'services': {'8765': {'ok': True}, '8045': {'ok': True}}}
        bad = {'ok': False, 'detail': '8045 caído', 'services': {'8765': {'ok': True}, '8045': {'ok': False}}}
        with tempfile.TemporaryDirectory() as temp, patch.object(services, 'ROOT', Path(temp)), patch.object(services, 'cascada_status', side_effect=[bad, bad, good, bad]), patch.object(services, 'chat_status', return_value={'ok': True, 'cdp': True}), patch.object(services, 'git_status', return_value={'ok': True}), patch.object(services, 'http_json', return_value={'ok': True, 'service': 'panel_control'}):
            (Path(temp) / 'logs').mkdir()
            m.cycle()
            m.cycle()
            self.assertEqual(m.icon.notify.call_count, 1)
            m.cycle()
            m.cycle()
            self.assertEqual(m.icon.notify.call_count, 2)

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = panel.Server(('127.0.0.1', 0), panel.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def post(self, name, token=panel.TOKEN, origin='http://127.0.0.1:8787'):
        req = urllib.request.Request(self.url + '/api/actions/' + name, data=b'{}', headers={'Host': '127.0.0.1:8787', 'X-Control-Token': token, 'Origin': origin, 'Content-Type': 'application/json'})
        return urllib.request.urlopen(req, timeout=5)

    def test_real_routes_dispatch_all_buttons(self):
        with patch.object(services, 'action', return_value={'ok': True, 'detail': 'tested'}) as action:
            for name in ('test-cascada', 'chrome-hidden', 'chrome-login', 'git-pull'):
                with self.post(name) as response:
                    self.assertEqual(response.status, 200)
                    self.assertTrue(json.load(response)['ok'])
                action.assert_called_with(name)

    def test_foreign_origin_and_missing_token_rejected(self):
        with patch.object(services, 'action') as action:
            for token, origin in (('', 'http://127.0.0.1:8787'), (panel.TOKEN, 'https://example.com')):
                with self.assertRaises(urllib.error.HTTPError) as error:
                    self.post('chrome-hidden', token, origin)
                self.assertEqual(error.exception.code, 403)
                error.exception.close()
            action.assert_not_called()

if __name__ == '__main__':
    unittest.main()
