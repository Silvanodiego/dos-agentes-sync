import json,sqlite3,socket,time
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
def rows(p,q):
 try:
  c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=2);c.row_factory=sqlite3.Row;r=[dict(x) for x in c.execute(q)];c.close();return r
 except Exception as e:return {'error':str(e)}
def port(n):
 try:
  with socket.create_connection(('127.0.0.1',n),timeout=1):return True
 except OSError:return False
def status():
 db=BASE_DIR/'memoria_reloj/estado_puente.db'
 data = {'manager':rows(Path.home()/'.antigravity-agent/cloud_accounts.db','select name,status,last_used from accounts'),'salud':rows(db,'select agente,estado,exitos,fallos,actualizado from salud_cuentas'),'cooldowns':rows(db,'select * from cooldown_familias'),'plugin_instalado':(Path.home()/'.codex/plugins/cache/maiquochuy-antigravity/agy-codex/0.1.0/scripts/agy-run.ps1').exists(),'puente_8765':port(8765),'cdp_9222':port(9222),'nota':'Puerto abierto no demuestra autenticacion o cuota.'}
 accounts=[]
 cooling=data['cooldowns'] if isinstance(data['cooldowns'],list) else []
 for n in range(1,5):
  account='cuenta-'+str(n)
  families={f:max([float(x['cooldown_until']) for x in cooling if x['cuenta']==account and x['familia']==f]+[0]) for f in ('sonnet','opus')}
  accounts.append({'cuenta':account,'cooldown_horas':{f:round(max(0,t-time.time())/3600,2) for f,t in families.items()},'elegible_local':any(t<=time.time() for t in families.values()),'cuota':'no comprobada en vivo; cooldown basado en errores registrados'})
 identity_path=BASE_DIR/'memoria_reloj/identidades_cuentas.json'
 try: data['identidades']=json.loads(identity_path.read_text(encoding='utf-8'))
 except (OSError,ValueError): data['identidades']={'estado':'pendiente de auditoria'}
 import sys
 sys.path.insert(0,str(BASE_DIR))
 from modulos_enjambre.model_router import claude_quota_exhausted
 data['contingencia_argon_habilitada']=claude_quota_exhausted()
 data['rotacion_cuentas']=accounts
 data['primaria_elegible']=next((x['cuenta'] for x in accounts if x['elegible_local']),None)
 return data
class H(BaseHTTPRequestHandler):
 def do_GET(self):
  api=self.path=='/api/status'
  html='<meta charset=utf-8><title>Antigravity</title><h1>Estado Antigravity local</h1><pre id=s></pre><script>async function u(){s.textContent=JSON.stringify(await(await fetch("/api/status")).json(),null,2)}u();setInterval(u,5000)</script>'
  body=(json.dumps(status(),ensure_ascii=False) if api else html).encode();self.send_response(200);self.send_header('Content-Type',('application/json' if api else 'text/html')+'; charset=utf-8');self.end_headers();self.wfile.write(body)
 def log_message(self,*a):pass
ThreadingHTTPServer(('127.0.0.1',8787),H).serve_forever()
