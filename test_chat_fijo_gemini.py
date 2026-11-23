"""Pruebas sin enviar mensajes ni ejecutar Codex real."""
from contextlib import nullcontext
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import chat_fijo_gemini as chat
import piloto_gemini as piloto

URL = "https://gemini.google.com/app/abc123?hl=es_419"


class ConfigTests(unittest.TestCase):
    def test_project_and_fallback_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "estado.db"
            connection = sqlite3.connect(db)
            connection.execute("CREATE TABLE config_chats(proyecto TEXT, url TEXT)")
            connection.executemany("INSERT INTO config_chats VALUES (?, ?)",
                                   [("DOS_AGENTES", URL), ("OTRO_PROYECTO", URL.replace("abc123", "otro"))])
            connection.commit()
            connection.close()
            before = db.read_bytes()
            self.assertEqual(chat.resolve_chat("otro proyecto", db).project, "OTRO_PROYECTO")
            self.assertTrue(chat.resolve_chat("no existe", db).fallback)
            self.assertEqual(before, db.read_bytes())

    def test_missing_database_not_created(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "missing.db"
            with self.assertRaises(chat.ChatFijoError):
                chat.resolve_chat("DOS_AGENTES", db)
            self.assertFalse(db.exists())

    def test_url_identity_ignores_language_not_chat(self):
        self.assertEqual(chat.chat_identity(URL), chat.chat_identity(URL.split("?")[0] + "/"))
        self.assertNotEqual(chat.chat_identity(URL), chat.chat_identity(URL.replace("abc123", "other")))

    def test_rejects_other_hosts_and_non_chat_urls(self):
        for url in ("http://gemini.google.com/app/abc", "https://evil.test/app/abc",
                    "https://gemini.google.com/app", "https://user:pass@gemini.google.com/app/abc"):
            with self.subTest(url=url), self.assertRaises(chat.ChatFijoError):
                chat.chat_identity(url)

    def test_closed_port_has_actionable_error(self):
        with patch.object(chat.socket, "create_connection", side_effect=TimeoutError), self.assertRaisesRegex(
                chat.ChatFijoError, "--remote-debugging-port=9222"):
            chat.check_port(0.1)


class ResponseTests(unittest.TestCase):
    def tracker(self):
        return chat.ResponseTracker({"key": 1, "text": "anterior", "complete": True})

    def test_never_returns_previous_response(self):
        tracker = self.tracker()
        old = {"key": 1, "text": "anterior", "complete": True}
        self.assertIsNone(tracker.observe(old, False, 0))
        self.assertIsNone(tracker.observe(old, False, 100))

    def test_stream_must_finish_and_be_stable(self):
        tracker = self.tracker()
        new = {"key": 2, "text": "respuesta", "complete": True}
        self.assertIsNone(tracker.observe(new, True, 0))
        self.assertIsNone(tracker.observe(new, True, 10))
        self.assertIsNone(tracker.observe(new, False, 11))
        self.assertEqual(tracker.observe(new, False, 14), "respuesta")

    def test_changed_text_restarts_stability(self):
        tracker = self.tracker()
        new = {"key": 2, "text": "parte", "complete": True}
        tracker.observe(new, False, 0)
        new = dict(new, text="respuesta completa")
        self.assertIsNone(tracker.observe(new, False, 4))
        self.assertIsNone(tracker.observe(new, False, 6))
        self.assertEqual(tracker.observe(new, False, 7), "respuesta completa")

    def test_no_completion_hint_no_early_return(self):
        tracker = self.tracker()
        new = {"key": 2, "text": "respuesta", "complete": False}
        tracker.observe(new, False, 0)
        self.assertIsNone(tracker.observe(new, False, 100))


class PilotTests(unittest.TestCase):
    def test_marker_must_be_own_line(self):
        self.assertTrue(piloto.delivery_complete("Terminado\n[ENTREGA_FINAL]\nResumen"))
        self.assertFalse(piloto.delivery_complete("Todavía no usar [ENTREGA_FINAL]."))

    def run_pilot(self, answers=None, preflight_error=None):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            connection = MagicMock()
            connection.__enter__.return_value = connection
            connection.ask.side_effect = answers or []
            connection.prepare.side_effect = preflight_error
            with patch.object(piloto, "ROOT", folder), \
                    patch.object(piloto, "resolve_folder", return_value=folder), \
                    patch.object(piloto, "resolve_chat", return_value=chat.ChatConfig("DOS_AGENTES", URL, False)), \
                    patch.object(piloto, "chat_lock", return_value=nullcontext()), \
                    patch.object(piloto, "GeminiChat", return_value=connection), \
                    patch.object(piloto, "codex_step", return_value="Avance verificado") as step, \
                    patch("sys.stdout", new_callable=io.StringIO), patch("sys.stderr", new_callable=io.StringIO):
                result = piloto.main(["--project", "DOS_AGENTES", "--task", "Tarea autorizada", "--max-turns", "2"])
            return result, step.call_count, connection.ask.call_count

    def test_preflight_failure_does_not_run_codex(self):
        self.assertEqual(self.run_pilot(preflight_error=chat.ChatFijoError("CDP cerrado")), (2, 0, 0))

    def test_final_delivery_stops_after_first_step(self):
        self.assertEqual(self.run_pilot(["[ENTREGA_FINAL]\nListo"]), (0, 1, 1))

    def test_next_instruction_then_delivery(self):
        self.assertEqual(self.run_pilot(["Revisá las pruebas", "[ENTREGA_FINAL]"]), (0, 2, 2))

    def test_turn_limit_stops(self):
        self.assertEqual(self.run_pilot(["Seguí", "Revisá"]), (3, 2, 2))

    def test_cancellation_stops_child_process(self):
        with tempfile.TemporaryDirectory() as temp:
            process = MagicMock()
            process.communicate.side_effect = KeyboardInterrupt
            with patch.object(piloto.shutil, "which", return_value="codex.exe"), \
                    patch.object(piloto.subprocess, "Popen", return_value=process), \
                    patch.object(piloto, "stop_process") as stop:
                with self.assertRaises(KeyboardInterrupt):
                    piloto.codex_step(Path(temp), "tarea", Path(temp) / "salida.txt", 1)
                stop.assert_called_once_with(process)


if __name__ == "__main__":
    unittest.main()
