"""Pruebas aisladas: sin cuentas reales, red, prompts ni logs de produccion."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bridge_server as bridge

class RotationTests(unittest.TestCase):
    def run_rotation(self, error):
        accounts = [("account1", "cuenta1"), ("account2", "cuenta2")]
        response = io.BytesIO(json.dumps({"choices": [{"message": {"content": "OK"}}]}).encode())
        with patch.object(bridge, "active_accounts", return_value=accounts), \
             patch.object(bridge, "rotation_log") as log, \
             patch.object(bridge.urllib.request, "urlopen", side_effect=[error, response]) as call:
            code, result = bridge.ask_accounts({}, "prueba sintetica")
        self.assertEqual((code, result["account"], result["response"]), (200, "cuenta2", "OK"))
        self.assertEqual([c.args[0].get_header("X-antigravity-account-id") for c in call.call_args_list], ["account1", "account2"])
        self.assertTrue(all(c.kwargs["timeout"] <= bridge.ATTEMPT_TIMEOUT for c in call.call_args_list))
        log.assert_called_once_with(1, "timeout" if isinstance(error, TimeoutError) else "http_" + str(error.code), 2)

    def test_429_rotates_to_account2(self):
        self.run_rotation(urllib.error.HTTPError("http://local", 429, "quota", {}, None))

    def test_503_rotates_to_account2(self):
        self.run_rotation(urllib.error.HTTPError("http://local", 503, "unavailable", {}, None))

    def test_timeout_rotates_to_account2(self):
        self.run_rotation(TimeoutError())

    def test_four_accounts_exhausted(self):
        with patch.object(bridge, "active_accounts", return_value=[(str(i), "cuenta") for i in range(4)]), \
             patch.object(bridge, "rotation_log"), \
             patch.object(bridge.urllib.request, "urlopen", side_effect=TimeoutError()) as call:
            code, result = bridge.ask_accounts({}, "prueba sintetica")
        self.assertEqual(code, 502)
        self.assertEqual(result["error"], "all_models_failed")
        self.assertEqual(call.call_count, 4)

    def test_deadline_stops_requests(self):
        with patch.object(bridge, "active_accounts", return_value=[("1", "cuenta")]), \
             patch.object(bridge, "rotation_log"), \
             patch.object(bridge.time, "monotonic", side_effect=[0, bridge.REQUEST_BUDGET + 1]), \
             patch.object(bridge.urllib.request, "urlopen") as call:
            code, result = bridge.ask_accounts({}, "prueba sintetica")
        self.assertEqual(code, 502)
        call.assert_not_called()

if __name__ == "__main__":
    unittest.main()
