"""Panel de control independiente, exclusivamente en localhost:8787."""
import json
import logging
import secrets
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import monitor_services as services

TOKEN = secrets.token_urlsafe(32)
HTML = r'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Control · Dos Agentes</title>
<style>:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#10141e;color:#e5eaf5;font:15px system-ui;padding:28px;max-width:1500px;margin:auto}header{display:flex;justify-content:space-between;align-items:center}h1{font-size:25px}small{color:#9aa9c4}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin:20px 0}article,.logs{background:#1b2332;border:1px solid #303d54;border-radius:14px;padding:20px}h2{font-size:16px;letter-spacing:.06em;margin-top:0}.status{font-weight:600;margin:16px 0;min-height:42px}.ok{color:#55dc9a}.bad{color:#ff7989}button{background:#2e405d;border:1px solid #526688;color:white;padding:10px 13px;border-radius:8px;cursor:pointer;margin:4px 5px 4px 0}button:disabled{opacity:.5}a{color:#8cbcff}ul{padding-left:18px;max-height:110px;overflow:auto}pre{white-space:pre-wrap;overflow:auto;font-size:12px;height:230px;color:#bfcce1}#message{min-height:24px;color:#b4c9ed;white-space:pre-wrap}@media(max-width:850px){.cards{grid-template-columns:1fr}body{padding:15px}}</style>
<header><h1>Panel de Control · Dos Agentes</h1><small id="updated">Actualizando…</small></header>
<div class="cards"><article><h2>CASCADA AG</h2><small>8765 · Script + 8045 · Antigravity</small><div id="cascada" class="status">Consultando…</div><button data-action="test-cascada">Probar Cascada AG</button></article>
<article><h2>CHAT FIJO GEMINI</h2><small>Chrome · CDP 9222</small><div id="chat" class="status">Consultando…</div><ul id="projects"></ul><button data-action="chrome-hidden">Reiniciar Chrome oculto</button><button data-action="chrome-login">Abrir Chrome visible (Login)</button></article>
<article><h2>GIT · dos-agentes-sync</h2><div id="git" class="status">Consultando…</div><p id="commit"></p><small id="branch"></small><p><button data-action="git-pull">Forzar Git Pull</button></p></article></div>
<div id="message" role="status"></div><section class="logs"><header><h2>ÚLTIMOS ERRORES</h2><button id="copy">Copiar error</button></header><small>Últimas 25 líneas reales de registros locales</small><pre id="errors"></pre></section>
<script>const token='__TOKEN__';let busy=false;const el=id=>document.getElementById(id);function status(id,data){el(id).textContent=data.detail;el(id).className='status '+(data.ok?'ok':'bad')}
async function refresh(){if(busy)return;busy=true;try{const r=await fetch('/api/status',{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const d=await r.json();status('cascada',d.cascada);status('chat',d.chat);status('git',d.git);el('commit').textContent=d.git.commit||'';el('branch').textContent='Rama: '+(d.git.branch||'?')+(d.git.dirty?' · Cambios locales':'');el('projects').replaceChildren();for(const p of d.chat.projects){const li=document.createElement('li'),a=document.createElement('a');a.textContent=p.project;a.href=p.url;a.target='_blank';a.rel='noopener noreferrer';li.append(a);el('projects').append(li)}el('errors').textContent=d.errors.lines.join('\n')||'Sin registros';el('updated').textContent='Actualizado '+new Date().toLocaleTimeString('es')}catch(e){el('updated').textContent='Panel sin respuesta: '+e.message}finally{busy=false}}
document.querySelectorAll('[data-action]').forEach(b=>b.onclick=async()=>{b.disabled=true;el('message').textContent='Ejecutando…';try{const r=await fetch('/api/actions/'+b.dataset.action,{method:'POST',headers:{'Content-Type':'application/json','X-Control-Token':token},body:'{}'});const d=await r.json();el('message').textContent=d.detail||JSON.stringify(d)}catch(e){el('message').textContent=e.message}finally{b.disabled=false;refresh()}});el('copy').onclick=async()=>{try{await navigator.clipboard.writeText(el('errors').textContent);el('message').textContent='Registro copiado'}catch(e){el('message').textContent='No se pudo copiar: '+e.message}};refresh();setInterval(refresh,5000);</script></html>'''

def snapshot():
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {key: pool.submit(fn) for key, fn in [('cascada', services.cascada_status), ('chat', services.chat_status), ('git', services.git_status), ('errors', services.errors_status)]}
        return {key: job.result() for key, job in jobs.items()}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, data, html=False):
        raw = data.encode('utf-8') if html else json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8' if html else 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def valid_host(self):
        return self.headers.get('Host') in ('127.0.0.1:8787', 'localhost:8787')

    def do_GET(self):
        if not self.valid_host():
            return self.send(403, {'error': 'Host inválido'})
        path = urlsplit(self.path).path
        routes = {'/api/health': lambda: {'ok': True, 'service': 'panel_control', 'port': 8787}, '/api/status': snapshot, '/api/cascada': services.cascada_status, '/api/chat': services.chat_status, '/api/git': services.git_status, '/api/errors': services.errors_status}
        try:
            if path == '/':
                return self.send(200, HTML.replace('__TOKEN__', TOKEN), html=True)
            if path in routes:
                return self.send(200, routes[path]())
            self.send(404, {'error': 'Endpoint desconocido'})
        except Exception as exc:
            logging.exception('GET falló')
            self.send(500, {'error': str(exc)})

    def do_POST(self):
        origin = self.headers.get('Origin')
        if not self.valid_host() or origin not in (None, 'http://127.0.0.1:8787', 'http://localhost:8787') or not secrets.compare_digest(self.headers.get('X-Control-Token', ''), TOKEN):
            return self.send(403, {'error': 'Solicitud no autorizada'})
        names = ('test-cascada', 'chrome-hidden', 'chrome-login', 'git-pull')
        name = self.path.removeprefix('/api/actions/')
        if self.path != '/api/actions/' + name or name not in names:
            return self.send(404, {'error': 'Acción desconocida'})
        self.send(200, services.action(name))

class Server(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

def refresh_remote():
    while True:
        try:
            p = services.run(['git', 'fetch', 'origin', 'main'], timeout=30)
            if p.returncode:
                logging.warning('git fetch: %s', p.stderr.strip())
        except Exception:
            logging.exception('No se pudo actualizar origin/main')
        time.sleep(300)

if __name__ == '__main__':
    services.setup_logging('panel_control')
    if services.singleton('panel_control'):
        threading.Thread(target=refresh_remote, daemon=True).start()
        logging.info('Panel iniciado en 127.0.0.1:8787')
        try:
            with Server(('127.0.0.1', 8787), Handler) as server:
                server.serve_forever()
        except Exception:
            logging.exception('No se pudo iniciar panel 8787')
            raise
