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
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "estado_puente.db"
ENDPOINT = "http://127.0.0.1:9222"
EDITOR = 'rich-textarea [contenteditable="true"], [contenteditable="true"][role="textbox"], textarea[aria-label]'
SEND = 'button.send-button:visible, button[aria-label="Send message"]:visible, button[aria-label="Enviar mensaje"]:visible'
STOP = 'button[aria-label*="Stop response"], button[aria-label*="Detener respuesta"], button[aria-label*="Stop generating"], button[aria-label*="Detener generación"], button.stop-button, button[data-test-id="stop-button"]'


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
  const nodes = [...document.querySelectorAll('model-response')];
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
        self.saw_busy = False

    def observe(self, snapshot: dict, busy: bool, now: float) -> str | None:
        self.saw_busy |= busy
        text = snapshot["text"].strip()
        fresh = (snapshot["key"] != self.baseline["key"] or text != self.baseline["text"])
        current = (snapshot["key"], text)
        if current != self.last or busy:
            self.last, self.changed_at = current, now
        finished = not busy and (self.saw_busy or snapshot.get("complete", False))
        if fresh and text and finished and now - self.changed_at >= self.stable_seconds:
            return text
        return None


class GeminiChat:
    def __init__(self, config: ChatConfig, connect_timeout: float = 5):
        self.config, self.connect_timeout = config, connect_timeout
        self.runtime = self.browser = self.page = None

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
        if chat_identity(self.page.url) != target:
            raise ChatFijoError("Gemini redirigió a otro chat o al login; abrí la sesión del chat configurado.")
        self.page.locator(EDITOR).first.wait_for(state="visible", timeout=15000)
        if visible(self.page.locator(STOP)):
            raise ChatFijoError("Gemini ya está generando. Se conserva esa respuesta sin enviar otra consulta.")

    def ask(self, prompt: str, timeout: float = 180) -> str:
        if not prompt.strip():
            raise ChatFijoError("El mensaje no puede estar vacío.")
        if self.page is None:
            self.prepare()
        target = chat_identity(self.config.url)
        if chat_identity(self.page.url) != target:
            raise ChatFijoError("La pestaña cambió de chat; no se envió el mensaje.")
        if visible(self.page.locator(STOP)):
            raise ChatFijoError("El chat ya está generando una respuesta.")
        editor = self.page.locator(EDITOR).first
        draft = editor.inner_text() if editor.get_attribute("contenteditable") else editor.input_value()
        if draft.strip():
            raise ChatFijoError("Hay un borrador en el editor; se conserva sin sobrescribirlo.")
        tracker = ResponseTracker(self.page.evaluate(SNAPSHOT_JS))
        editor.fill(prompt)
        self.page.locator(SEND).first.click(timeout=10000)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if chat_identity(self.page.url) != target:
                raise ChatFijoError("La pestaña cambió de chat durante la respuesta.")
            answer = tracker.observe(self.page.evaluate(SNAPSHOT_JS),
                                     visible(self.page.locator(STOP)), time.monotonic())
            if answer is not None:
                return answer
            self.page.wait_for_timeout(500)
        raise ChatFijoError("Tiempo agotado esperando la respuesta completa de Gemini. No se reenvió el mensaje; revisá la pestaña antes de reintentar.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="DOS_AGENTES")
    parser.add_argument("--message", help="Si falta, se lee de stdin; no se usa con --check")
    parser.add_argument("--check", action="store_true", help="Solo conecta a CDP; no abre pestañas ni envía mensajes")
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
                print(chat.ask(message, args.timeout))
        return 0
    except (ChatFijoError, ValueError) as exc:
        print("ERROR_CHAT_FIJO: " + str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR_CHAT_FIJO: {type(exc).__name__}: {exc}. No se reintentó el envío.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
