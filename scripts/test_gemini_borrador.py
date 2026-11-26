import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import chat_fijo_gemini as module


class DraftTests(unittest.TestCase):
    def make_chat(self, editable=True, clears=True):
        chat = module.GeminiChat.__new__(module.GeminiChat)
        chat.page = MagicMock()
        chat.creating = False
        chat.web_model = "modelo mock"
        chat.model_note = ""
        chat.wait_ready = MagicMock()
        chat.select_best_model = MagicMock()
        chat.ensure_target = MagicMock()
        chat.capture_chat = MagicMock()
        chat.generating = MagicMock(return_value=False)
        editor = MagicMock()
        editor.get_attribute.return_value = "true" if editable else None
        values = ["borrador previo", "" if clears else "borrador previo"]
        (editor.inner_text if editable else editor.input_value).side_effect = values
        chat.ready_editor = MagicMock(return_value=editor)
        return chat, editor

    def test_cli_flag_clears_existing_draft_and_returns_answer(self):
        chat, editor = self.make_chat()
        context = MagicMock()
        context.__enter__.return_value = chat
        config = SimpleNamespace(project="DOS_AGENTES")
        with patch.object(module, "resolve_chat", return_value=config), \
             patch.object(module, "chat_lock", return_value=contextlib.nullcontext()), \
             patch.object(module, "GeminiChat", return_value=context), \
             patch.object(module, "ResponseTracker") as tracker, \
             contextlib.redirect_stdout(io.StringIO()) as stdout, \
             contextlib.redirect_stderr(io.StringIO()):
            tracker.return_value.observe.return_value = "CONEXION_OK"
            result = module.main(["--project", "DOS_AGENTES", "--message", "consulta", "--limpiar-borrador"])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue(), "CONEXION_OK\n")
        self.assertEqual(editor.fill.call_args_list, [unittest.mock.call(""), unittest.mock.call("consulta")])
        chat.page.locator.return_value.first.click.assert_called_once()

    def test_no_flag_preserves_draft_and_does_not_send(self):
        chat, editor = self.make_chat()
        with self.assertRaisesRegex(module.ChatFijoError, "Hay un borrador"):
            chat.ask("consulta")
        editor.fill.assert_not_called()
        chat.page.locator.assert_not_called()
        self.assertFalse(chat.message_sent)

    def test_textarea_is_cleared_before_send(self):
        chat, editor = self.make_chat(editable=False)
        with patch.object(module, "ResponseTracker") as tracker:
            tracker.return_value.observe.return_value = "OK"
            self.assertEqual(chat.ask("consulta", limpiar_borrador=True), "OK")
        self.assertEqual(editor.fill.call_args_list, [unittest.mock.call(""), unittest.mock.call("consulta")])

    def test_failed_clear_does_not_send(self):
        chat, editor = self.make_chat(clears=False)
        with self.assertRaisesRegex(module.ChatFijoError, "No se pudo limpiar"):
            chat.ask("consulta", limpiar_borrador=True)
        editor.fill.assert_called_once_with("")
        chat.page.locator.assert_not_called()
        self.assertFalse(chat.message_sent)


if __name__ == "__main__":
    unittest.main()
