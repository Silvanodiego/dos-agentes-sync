"""Monitor pystray independiente con watchdog acotado a Chrome y panel."""
import json
import logging
import threading
import time
import webbrowser
import pystray
from PIL import Image, ImageDraw
import monitor_services as services

def icon_image(color):
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((5, 5, 59, 59), fill=color, outline='#dbe7fa', width=3)
    draw.text((22, 22), 'AG', fill='#10141e')
    return image

class Monitor:
    def __init__(self):
        self.stop = threading.Event()
        self.last = {}
        self.notified = set()
        self.status = {'cascada': {'detail': 'Comprobando…'}, 'chat': {'detail': 'Comprobando…'}, 'git': {'detail': 'Comprobando…'}}
        self.icon = pystray.Icon('DosAgentesMonitor', icon_image('#efba49'), 'Dos Agentes · comprobando', menu=pystray.Menu(
            pystray.MenuItem(lambda _: 'Cascada AG: ' + self.status['cascada']['detail'], None, enabled=False),
            pystray.MenuItem(lambda _: 'Chat Fijo: ' + self.status['chat']['detail'], None, enabled=False),
            pystray.MenuItem(lambda _: 'Git: ' + self.status['git']['detail'], None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Abrir Panel (8787)', lambda *_: webbrowser.open('http://127.0.0.1:8787')),
            pystray.MenuItem('Abrir Chrome visible (Login)', lambda *_: self.do_action('chrome-login')),
            pystray.MenuItem('Forzar Git Pull', lambda *_: self.do_action('git-pull')),
            pystray.MenuItem('Reiniciar Chrome oculto', lambda *_: self.do_action('chrome-hidden')),
            pystray.MenuItem('Salir del monitor', self.exit)))

    def do_action(self, name):
        def worker():
            result = services.action(name)
            if not result['ok']:
                self.icon.notify(result['detail'][:200], 'Dos Agentes')
        threading.Thread(target=worker, daemon=True).start()

    def exit(self, *_):
        self.stop.set()
        self.icon.stop()

    def recover(self, name):
        now = time.monotonic()
        if now - self.last.get(name, -300) < 300:
            return False
        self.last[name] = now
        self.icon.icon = icon_image('#efba49')
        self.icon.title = 'Dos Agentes · recuperando ' + name
        logging.warning('Watchdog: intento de recuperación de %s', name)
        if name == '9222':
            services.action('chrome-hidden')
        else:
            services.start_panel()
        self.stop.wait(5)
        return True

    def cycle(self):
        self.status = {'cascada': services.cascada_status(), 'chat': services.chat_status(), 'git': services.git_status()}
        chat = self.status['chat']
        if not chat['cdp'] and self.recover('9222'):
            chat = self.status['chat'] = services.chat_status()
        def panel_ok():
            try:
                data = services.http_json(8787, '/api/health')
                return data.get('ok') is True and data.get('service') == 'panel_control'
            except Exception:
                return False
        panel = panel_ok()
        if not panel and self.recover('8787'):
            panel = panel_ok()
        failures = {}
        for port, data in self.status['cascada']['services'].items():
            if not data['ok']:
                failures[port] = 'Cascada AG: ' + port + ' no responde. Revisar servicio manualmente.'
        if not chat['ok']:
            failures['chat'] = chat['detail']
        if not panel:
            failures['panel'] = 'Panel 8787 caído después del intento de recuperación.'
        self.notified.intersection_update(failures)
        for incident, detail in failures.items():
            if incident not in self.notified:
                logging.error('%s', detail)
                self.icon.notify(detail[:240], 'Dos Agentes · requiere atención')
                self.notified.add(incident)
        self.icon.icon = icon_image('#f06475' if failures else '#4dd99a')
        self.icon.title = ('Dos Agentes · ' + ' / '.join(failures))[:127] if failures else 'Dos Agentes · todos los servicios OK'
        self.icon.update_menu()
        state = {'color': 'red' if failures else 'green', 'failures': failures, 'checked_at': time.time(), 'status': self.status}
        target = services.ROOT / 'logs/tray_status.json'
        temp = target.with_suffix('.tmp')
        temp.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
        temp.replace(target)

    def watch(self):
        while not self.stop.is_set():
            try:
                self.cycle()
            except Exception:
                logging.exception('Error en ciclo del monitor')
                self.icon.icon = icon_image('#f06475')
            self.stop.wait(15)

    def run(self):
        def setup(icon):
            icon.visible = True
            threading.Thread(target=self.watch, daemon=True).start()
        self.icon.run(setup)

if __name__ == '__main__':
    services.setup_logging('tray_monitor')
    if services.singleton('tray_monitor'):
        Monitor().run()
