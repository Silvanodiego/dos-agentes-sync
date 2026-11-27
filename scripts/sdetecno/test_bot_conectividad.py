"""Pruebas aisladas de reclamos de conectividad; sin red ni datos reales."""
import importlib.util
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("bot_candidate", Path(__file__).with_name("bot_experiencia.py"))
bot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bot)


class BackendFalso:
    PRECIOS = {"7d": 100, "1mes": 300}
    NOMBRES_PLAN = {"7d": "7 días", "1mes": "1 mes"}
    DURACIONES = {}

    def __init__(self):
        self._bot_active_lock = {}
        self.persistencias = 0

    def resolver_chat_id(self, chat):
        return "cliente_resuelto@c.us" if chat == "cliente_prueba@lid" else chat

    def _mac_de_chat(self, chat):
        return None

    def _bot_guardar_estado(self):
        self.persistencias += 1
        return True


class ConectividadTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bot_conectividad_")
        self.old_db = bot.DB
        bot.DB = Path(self.temp.name) / "aislado.sqlite3"
        self.backend = BackendFalso()
        self.links = patch.object(bot, "make_link", return_value={"plan": "7d", "precio": 100, "at": time.time(), "renew": False, "dispositivos": 1})
        self.link = self.links.start()
        self.quotes = patch.object(bot, "quote", return_value="ENLACE_SIMULADO")
        self.quotes.start()
        self.menus = patch.object(bot, "menu", return_value="MENU_SIMULADO")
        self.menu = self.menus.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(setattr, bot, "DB", self.old_db)
        self.addCleanup(self.menus.stop)
        self.addCleanup(self.quotes.stop)
        self.addCleanup(self.links.stop)

    def filas(self, table):
        with bot.database() as c:
            return [dict(x) for x in c.execute("SELECT * FROM " + table)]

    def reclamar(self, texto, lote="lote_prueba", chat="cliente_prueba@lid"):
        r = bot.commerce(self.backend, chat, texto, lote)
        self.assertTrue(r.get("handled"), texto)
        self.assertNotEqual(r.get("respuesta"), "MENU_SIMULADO", texto)
        self.assertNotEqual(r.get("respuesta"), "ENLACE_SIMULADO", texto)
        self.link.assert_not_called()
        self.menu.assert_not_called()
        casos = self.filas("support")
        self.assertEqual(len(casos), 1, texto)
        self.assertEqual(bot.case_family(casos[0]["reason"]), "acceso")
        self.assertEqual(casos[0]["chat"], "cliente_resuelto@c.us")
        self.assertIn(str(casos[0]["id"]), r["respuesta"])
        self.assertNotRegex(r["respuesta"].lower(), r"red (?:está |esta )?caída|plan vigente|ya (?:está |esta )?resuelto")
        return r

    def test_reclamos_explicitos_antes_del_menu(self):
        frases = [
            "Buen día, sigo sin poder conectarme a wifi de la red",
            "Sigo sin poder conectarme al Wi-Fi",
            "No puedo conectarme al wifi",
            "No me puedo conectar",
            "No puedo navegar",
            "El wifi no funciona",
            "Internet no me anda",
            "No tengo internet",
            "Estoy sin conexión",
            "No hay wifi",
            "Se cortó internet",
            "El internet anda mal",
            "El wifi no me deja conectarme",
            "Pagué y sigo sin servicio",
            "Estoy conectado pero sin internet",
            "Se me corta el wifi",
            "El wifi no me anda",
            "Sigo sin acceso al wifi",
            "El wifi se desconecta a cada rato",
        ]
        for n, texto in enumerate(frases):
            with self.subTest(texto=texto):
                self.reclamar(texto, "lote_" + str(n))

    def test_plan_y_falla_no_generan_link(self):
        for n, texto in enumerate([
            "Tengo un plan de 7 días y no puedo conectarme al wifi",
            "Pagué 7 días pero sigo sin poder conectarme",
            "Necesito renovar 1 mes porque no funciona internet",
            "Mi plan de 7 días está activado pero no tengo internet",
        ]):
            with self.subTest(texto=texto):
                self.reclamar(texto, "plan_falla_" + str(n))

    def test_consultas_comerciales_no_crean_soporte(self):
        for texto in ["Precios del wifi", "No tengo código", "No tengo código para wifi", "No puedo pagar wifi", "wifi", "El wifi no se corta, quiero pagar7d", "Se me cortó la luz, quiero comprar wifi7d", "Cuánto cuesta 7 días", "Cómo me conecto al wifi", "Quiero comprar un plan de 7 días"]:
            with self.subTest(texto=texto):
                bot.commerce(self.backend, "cliente_prueba@lid", texto, "comercial")
                self.assertEqual(self.filas("support"), [])
        self.assertTrue(self.link.called)

    def test_pago_realizado_no_desvia_reclamo_a_pago(self):
        for n, texto in enumerate([
            "Pagué por Mercado Pago y no funciona internet",
            "Mi plan ya está pago y no tengo internet",
            "El servicio está pagado y no funciona el wifi",
        ]):
            with self.subTest(texto=texto):
                self.reclamar(texto, "pagado_" + str(n))

    def test_pago_sin_internet_preserva_ayuda_inicial(self):
        for texto in ["No tengo internet para pagar el plan de 7 días", "No tengo internet para abrir el link de pago", "El plan no está pago y no tengo internet para pagar"]:
            with self.subTest(texto=texto):
                r = bot.commerce(self.backend, "cliente_prueba@lid", texto, "pago")
                self.assertTrue(r["handled"])
                self.assertIn("conexión disponible", r["respuesta"])
                self.assertEqual(self.filas("support"), [])
                self.link.assert_not_called()
                self.menu.assert_not_called()

    def test_ayuda_para_pagar_preserva_ticket_de_pago(self):
        r = bot.commerce(self.backend, "cliente_prueba@lid", "Ayuda para pagar", "pago")
        self.assertTrue(r["handled"])
        self.assertEqual(bot.case_family(self.filas("support")[0]["reason"]), "pago")
        self.link.assert_not_called()

    def test_ticket_unico_por_lote_y_familia(self):
        self.reclamar("No puedo conectarme al wifi", "lote_unico")
        self.reclamar("Sigo sin poder conectarme al wifi", "lote_unico")
        self.assertEqual(len(self.filas("support_batches")), 1)
        self.reclamar("Internet no funciona", "otro_lote")
        self.assertEqual(len(self.filas("support_batches")), 2)
        self.assertEqual(len(self.filas("support")), 1)

    def test_lid_y_chat_resuelto_comparten_caso(self):
        self.reclamar("No puedo conectarme al wifi", "lid")
        self.reclamar("Sigo sin poder conectarme", "pn", "cliente_resuelto@c.us")
        self.assertEqual(len(self.filas("support")), 1)

    def test_no_cambia_oferta_comercial_existente(self):
        previo = {"offered": "7d", "offered_at": time.time(), "quote": {"plan": "7d", "precio": 100, "at": time.time()}}
        bot.state("cliente_prueba@lid", previo)
        self.reclamar("El plan de 7 días no me permite navegar en internet")
        self.assertEqual(bot.state("cliente_prueba@lid"), previo)

    def test_respuesta_verificada_llega_a_finalizar(self):
        chat = "cliente_prueba@lid"
        texto = "Sigo sin poder conectarme al wifi"
        self.backend._bot_active_lock[chat] = {"lock_id": "candado_sintetico"}
        payload = {"chat_id": chat, "lock_id": "candado_sintetico", "texto": texto}
        directo = self.reclamar(texto)
        bot.remember(self.backend, payload, directo)
        final = bot.finalize(self.backend, dict(payload, respuesta="MENU_SIMULADO"))
        self.assertTrue(final["ok"])
        self.assertTrue(final["respuesta"].endswith(directo["respuesta"]))
        self.menu.assert_not_called()
        self.assertEqual(len(self.filas("support")), 1)
        self.assertGreater(self.backend.persistencias, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)