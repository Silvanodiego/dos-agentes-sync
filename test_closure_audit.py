"""Regression checks for closure verdicts; no services or databases are touched."""
import unittest
from contextlib import ExitStack
from unittest.mock import patch

import agy_passthrough as agy


class ClosureAuditTests(unittest.TestCase):
    def evaluate(self, first, second, mode="verify"):
        with ExitStack() as stack:
            for name, value in (
                ("ensure_services_running", None),
                ("detect_project_and_brain", ("TEST", "", "", ".")),
                ("build_repo_snapshot", "SNAPSHOT"),
                ("rotate_account", ("test", "test")),
                ("call_bridge_8765", second),
                ("_ts_compress", "COMPRESSED"),
            ):
                stack.enter_context(patch.object(agy, name, return_value=value))
            manager = stack.enter_context(patch.object(agy, "call_manager", return_value=first))
            stack.enter_context(patch.object(agy.sqlite3, "connect", side_effect=RuntimeError("no database writes")))
            result = agy.evaluate_factory("PEDIDO ORIGINAL: A B C. PENDIENTE: C", mode=mode)
            if mode == "verify":
                self.assertIn("PENDIENTE: C", manager.call_args.args[0])
                self.assertIn("confirmacion del sitio", manager.call_args.args[0])
            return result

    def test_partial_rejected_despite_successful_transport(self):
        result = self.evaluate("COMPLETO_100%", "INCOMPLETO_FALTA: C sin enviar")
        self.assertTrue(result["transport_ok"])
        self.assertFalse(result["ok"])

    def test_both_exact_approvals_required(self):
        self.assertTrue(self.evaluate("COMPLETO_100%", "COMPLETO_100%")["ok"])
        self.assertFalse(self.evaluate("COMPLETO_100% pero falta C", "COMPLETO_100%")["ok"])

    def test_work_advice_remains_successful(self):
        self.assertTrue(self.evaluate("Consejo A", "Consejo B", mode="work")["ok"])


if __name__ == "__main__":
    unittest.main()
