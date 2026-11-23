"""Chat fijo de Gemini por CDP. No utiliza ni modifica Cascada AG."""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import sys
import time
import unicodedata
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "estado_puente.db"
ENDPOINT = "http://127.0.0.1:9222"
EDITOR = 'rich-textarea [contenteditable="true"], [contenteditable="true"][role="textbox"], textarea[aria-label]'
SEND = 'button.send-button:visible, button[aria-label="Send message"]:visible, button[aria-label="Enviar mensaje"]:visible'

# El filtro se aplica a aria-label, title y texto, nunca al nombre de la cuenta.
GENERATION_JS = r"""() => {
  const norm = s => (s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  return [...document.querySelectorAll('button, [role="button"]')].some(b => {
    if (!b.getClientRects().length || getComputedStyle(b).visibility === 'hidden') return false;
    const label = norm([b.getAttribute('aria-label'), b.title, b.innerText].join(' '));
    if (/audio|voz|voice|microfono|mic|escuchar|listen/.test(label)) return false;
    return /detener (?:la )?(?:respuesta|generacion)|stop (?:response|generating|generation)/.test(label)
      || b.matches('button.stop-button, button[data-test-id="stop-button"]');
  });
}"""


def normalized(value: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower())
                   if unicodedata.category(c) != 'Mn')


def model_priority(label: str) -> int:
    text = normalized(label)
    if re.search(r'\b(pro|ultra|advanced)\b', text):
        return 3
    if re.search(r'\b(thinking|razonamiento|pensamiento|pensar|neon)\b|analisis mas profundo', text):
        return 2
    if re.search(r'\b(fast|flash|rapido|hydrogen)\b|ayuda todos los dias', text):
        return 1
    return 0


def model_available(label: str, disabled: bool = False) -> bool:
    return not disabled and not re.search(
        r'agotad|sin cuota|no disponible|unavailable|quota exceeded|out of quota|'
        r'(?:limit|limite).*?(?:reached|alcanz)|alcanz.*?limite|'
        r'upgrade|mejorar (?:el )?plan|suscrib|subscribe', normalized(label))


class ChatFijoError(RuntimeError):
    pass


def normalize_project(value: str) -> str:
    return value.strip().replace(" ", "_").upper()


def chat_identity(url: str) -> tuple[str, str]:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname != "gemini.google.com"
            or parsed.username or parsed.password or parsed.port not in (None, 443)
            or not re.fullmatch(r"/app/[A-Za-z0-9_-]+/?", parsed.path)):
        raise ChatFijoError("La URL debe identificar un chat fijo https://gemini.google.com/app/ID.")
    return parsed.hostname, parsed.path.rstrip("/")


@dataclass(frozen=True)
class ChatConfig:
    project: str
    url: str
    fallback: bool


def resolve_chat(project: str, database: Path = DATABASE) -> ChatConfig:
    try:
        with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as db:
            rows = db.execute("SELECT proyecto, url FROM config_chats").fetchall()
    except sqlite3.Error as exc:
        raise ChatFijoError(f"No se pudo leer config_chats en {database}: {exc}") from exc
    chats = {normalize_project(name): (name, url) for name, url in rows}
    key = normalize_project(project)
    selected = chats.get(key) or chats.get("DOS_AGENTES")
    if not selected:
        raise ChatFijoError("Proyecto no registrado y falta el fallback DOS_AGENTES en config_chats.")
    name, url = selected
    chat_identity(url)
    return ChatConfig(name, url, key not in chats)


def check_port(timeout: float = 3) -> None:
    try:
        with socket.create_connection(("127.0.0.1", 9222), timeout=timeout):
            pass
    except OSError as exc:
        raise ChatFijoError(
            "CDP 127.0.0.1:9222 no responde. Falta abrir Chrome/Edge con "
            "--remote-debugging-port=9222 y un --user-data-dir dedicado, "
            "o restablecer el túnel CDP existente. No se inició ningún paso de Codex."
        ) from exc


@contextmanager
def chat_lock(url: str):
    """El sistema operativo libera el bloqueo aunque el proceso muera."""
    folder = ROOT / ".sync-local" / "chat-fijo"
    folder.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(repr(chat_identity(url)).encode()).hexdigest()[:24]
    with (folder / (key + ".lock")).open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ChatFijoError("Otro proceso está usando este chat fijo; no se enviaron mensajes.") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


# Identidad del nodo, no cantidad de nodos: resiste la virtualización del historial.
SNAPSHOT_JS = """() => {
  window.__chatFijoNodes ??= new WeakMap();
  window.__chatFijoCounter ??= 0;
  const nodes = [...document.querySelectorAll('model-response, response-container')];
  const last = nodes.at(-1);
  if (!last) return {key: null, text: '', complete: false};
  if (!window.__chatFijoNodes.has(last))
    window.__chatFijoNodes.set(last, ++window.__chatFijoCounter);
  const textNode = last.querySelector('.model-response-text .markdown, .markdown, message-content');
  const text = textNode ? textNode.innerText.trim() : '';
  const complete = [...last.querySelectorAll('button')].some(b =>
    /copy|copiar/i.test(b.getAttribute('aria-label') || b.getAttribute('title') || ''));
  return {key: window.__chatFijoNodes.get(last), text, complete};
}"""


def visible(locator) -> bool:
    return any(item.is_visible() for item in locator.all())


class ResponseTracker:
    """Exige una respuesta nueva, fin de generación y texto estable."""
    def __init__(self, baseline: dict, stable_seconds: float = 3):
        self.baseline = baseline
        self.stable_seconds = stable_seconds
        self.last = None
        self.changed_at = None

    def observe(self, snapshot: dict, busy: bool, now: float) -> str | None:
        text = snapshot["text"].strip()
        fresh = (snapshot["key"] != self.baseline["key"] or text != self.baseline["text"])
        current = (snapshot["key"], text)
        if current != self.last or busy:
            self.last, self.changed_at = current, now
        finished = not busy
        if fresh and text and finished and now - self.changed_at >= self.stable_seconds:
            return text
        return None


class GeminiChat:
    def __init__(self, config: ChatConfig, connect_timeout: float = 5):
        self.config, self.connect_timeout = config, connect_timeout
        self.runtime = self.browser = self.page = None
        self.web_model = "no seleccionado (preparación pendiente)"
        self.model_note = ""

    def __enter__(self):
        check_port(min(self.connect_timeout, 3))
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ChatFijoError("Falta Playwright: ejecutá .venv\\Scripts\\python.exe -m pip install -r requirements_chat_fijo.txt") from exc
        try:
            self.runtime = sync_playwright().start()
            self.browser = self.runtime.chromium.connect_over_cdp(
                ENDPOINT, timeout=self.connect_timeout * 1000)
            if not self.browser.contexts:
                raise ChatFijoError("CDP respondió, pero no hay un contexto de navegador disponible.")
            return self
        except Exception as exc:
            self.__exit__(None, None, None)
            if isinstance(exc, ChatFijoError):
                raise
            raise ChatFijoError(f"No se pudo conectar por CDP a {ENDPOINT}: {exc}") from exc

    def __exit__(self, *_):
        # Desconectar Playwright. Nunca cerrar páginas, contextos ni el navegador remoto.
        if self.runtime:
            self.runtime.stop()
            self.runtime = None

    def check(self) -> dict:
        target = chat_identity(self.config.url)
        found = False
        for context in self.browser.contexts:
            for page in context.pages:
                try:
                    found |= chat_identity(page.url) == target
                except (ChatFijoError, ValueError):
                    pass
        return {"status": "ok", "endpoint": ENDPOINT, "project": self.config.project,
                "fallback": self.config.fallback, "chat_tab_open": found,
                "contexts": len(self.browser.contexts), "message_sent": False}

    def prepare(self):
        target = chat_identity(self.config.url)
        for context in self.browser.contexts:
            for page in context.pages:
                try:
                    if chat_identity(page.url) == target:
                        self.page = page
                        break
                except (ChatFijoError, ValueError):
                    pass
            if self.page:
                break
        if self.page is None:
            self.page = self.browser.contexts[0].new_page()
            self.page.goto(self.config.url, wait_until="domcontentloaded", timeout=20000)
        self.page.set_default_timeout(10000)
        self.wait_ready()

    def ensure_target(self):
        try:
            matches = chat_identity(self.page.url) == chat_identity(self.config.url)
        except (ChatFijoError, ValueError):
            matches = False
        if not matches:
            host = urlsplit(self.page.url).hostname
            if host == "accounts.google.com":
                raise ChatFijoError("Falta iniciar sesión de Google en la ventana abierta; no se envió el mensaje.")
            raise ChatFijoError("La URL fija redirigió fuera del chat configurado; verificá que esta cuenta tenga acceso a DOS_AGENTES. No se envió el mensaje.")

    def generating(self) -> bool:
        return self.page.evaluate(GENERATION_JS)

    def ready_editor(self):
        from playwright.sync_api import expect
        self.ensure_target()
        editor = self.page.locator(', '.join(part.strip() + ':visible' for part in EDITOR.split(','))).first
        expect(editor).to_be_visible(timeout=15000)
        expect(editor).to_be_enabled(timeout=10000)
        expect(editor).to_be_editable(timeout=10000)
        return editor

    def wait_ready(self):
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        self.page.wait_for_load_state("domcontentloaded", timeout=15000)
        try:
            self.page.wait_for_load_state("networkidle", timeout=5000)
        except PlaywrightTimeout:
            # Gemini mantiene conexiones: exigir además editor y ausencia de STOP.
            self.model_note = "networkidle agotó 5 s; se validó el editor y la generación"
        self.ready_editor()
        deadline = time.monotonic() + 15
        while self.generating():
            if time.monotonic() >= deadline:
                raise ChatFijoError("Gemini sigue generando; no se envió ni se canceló ninguna consulta.")
            self.page.wait_for_timeout(250)

    def select_best_model(self):
        """Solo interactúa con el menú de modelos; nunca suscripciones ni compras."""
        trigger = None
        for control in self.page.locator('button, [role="button"], [role="combobox"]').all():
            if not control.is_visible():
                continue
            metadata = control.evaluate("e => ({text:e.innerText, label:e.getAttribute('aria-label')||'', test:e.getAttribute('data-test-id')||'', cls:e.className||''})")
            name = metadata['text'].strip() or metadata['label']
            identity = normalized(metadata['test'] + ' ' + metadata['cls'] + ' ' + metadata['label'])
            if (re.search(r'model.selector|mode.menu|mode.picker|bard.mode|input.area.switch|selector.*modelo|seleccionar.*modelo', identity)
                    or (len(name) < 90 and model_priority(name) > 0
                        and not re.search(r'upgrade|suscrib|prueba', normalized(name)))):
                trigger = control
                self.web_model = name
                break
        if trigger is None:
            self.web_model = "no identificado (selector ausente)"
            return
        trigger.click(timeout=5000)
        options = self.page.locator('[role="menuitem"], [role="menuitemradio"], [role="option"], .mat-mdc-menu-content button')
        deadline = time.monotonic() + 3
        while not visible(options) and time.monotonic() < deadline:
            self.page.wait_for_timeout(100)
        ranked = []
        for index, option in enumerate(options.all()):
            if not option.is_visible():
                continue
            label = option.inner_text().strip() or option.get_attribute('aria-label') or ''
            disabled = not option.is_enabled() or option.get_attribute('aria-disabled') == 'true'
            if label and model_available(label, disabled):
                ranked.append((model_priority(label), -index, label, option))
        if not ranked:
            self.page.keyboard.press('Escape')
            raise ChatFijoError("El selector de modelos no ofreció opciones habilitadas verificables; no se envió el mensaje.")
        _, _, label, option = max(ranked, key=lambda item: item[:2])
        option.click(timeout=5000)
        self.page.wait_for_timeout(300)
        selected = trigger.inner_text().strip() or trigger.get_attribute('aria-label') or ''
        if not selected or (model_priority(label) and model_priority(selected) != model_priority(label)):
            raise ChatFijoError("No se pudo confirmar el modelo seleccionado; no se envió el mensaje.")
        self.web_model = selected

    def ask(self, prompt: str, timeout: float = 180) -> str:
        if not prompt.strip():
            raise ChatFijoError("El mensaje no puede estar vacío.")
        if self.page is None:
            self.prepare()
        else:
            self.wait_ready()
        self.select_best_model()
        self.ready_editor()
        self.page.wait_for_timeout(2000)
        editor = self.ready_editor()
        if self.generating():
            raise ChatFijoError("El chat empezó otra generación durante la estabilización; no se envió el mensaje.")
        draft = editor.inner_text() if editor.get_attribute("contenteditable") else editor.input_value()
        if draft.strip():
            raise ChatFijoError("Hay un borrador en el editor; se conserva sin sobrescribirlo.")
        tracker = ResponseTracker(self.page.evaluate(SNAPSHOT_JS))
        editor.fill(prompt)
        self.page.locator(SEND).first.click(timeout=10000)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.ensure_target()
            answer = tracker.observe(self.page.evaluate(SNAPSHOT_JS),
                                     self.generating(), time.monotonic())
            if answer is not None:
                return answer
            self.page.wait_for_timeout(500)
        raise ChatFijoError("Tiempo agotado esperando la respuesta completa de Gemini. No se reenvió el mensaje; revisá la pestaña antes de reintentar.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="DOS_AGENTES")
    parser.add_argument("--message", help="Si falta, se lee de stdin; no se usa con --check")
    parser.add_argument("--check", action="store_true", help="Solo conecta a CDP; no abre pestañas ni envía mensajes")
    parser.add_argument("--json-result", action="store_true", help="Devuelve modelo web y respuesta en JSON")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--connect-timeout", type=float, default=5)
    args = parser.parse_args(argv)
    if args.timeout <= 0 or args.connect_timeout <= 0:
        parser.error("Los tiempos deben ser positivos")
    try:
        config = resolve_chat(args.project)
        if args.check:
            with GeminiChat(config, args.connect_timeout) as chat:
                print(json.dumps(chat.check(), ensure_ascii=False))
        else:
            message = args.message if args.message is not None else sys.stdin.read()
            with chat_lock(config.url), GeminiChat(config, args.connect_timeout) as chat:
                try:
                    answer = chat.ask(message, args.timeout)
                    if args.json_result:
                        print(json.dumps({"model": chat.web_model, "response": answer,
                                          "note": chat.model_note}, ensure_ascii=False))
                    else:
                        print(answer)
                finally:
                    print("MODELO_WEB: " + chat.web_model, file=sys.stderr)
        return 0
    except (ChatFijoError, ValueError) as exc:
        print("ERROR_CHAT_FIJO: " + str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR_CHAT_FIJO: {type(exc).__name__}: {exc}. No se reintentó el envío.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
