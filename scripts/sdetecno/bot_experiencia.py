# Politica determinista y seguimiento durable del bot.
import json,re,sqlite3,time,unicodedata
from pathlib import Path
from contextlib import contextmanager
DB=Path(__file__).with_name('bot_experiencia.sqlite3')
def norm(x):return ''.join(c for c in unicodedata.normalize('NFD',str(x).lower()) if unicodedata.category(c)!='Mn')
@contextmanager
def database():
    c=sqlite3.connect(str(DB),timeout=10);c.row_factory=sqlite3.Row
    DB.chmod(0o600)
    c.executescript('''CREATE TABLE IF NOT EXISTS conversations(chat TEXT PRIMARY KEY,data TEXT);
CREATE TABLE IF NOT EXISTS support(id INTEGER PRIMARY KEY,chat TEXT,batch TEXT,reason TEXT,detail TEXT,state TEXT,created REAL,updated REAL,evidence TEXT DEFAULT '',UNIQUE(chat,batch));
CREATE TABLE IF NOT EXISTS support_events(id INTEGER PRIMARY KEY,case_id INTEGER,at REAL,action TEXT,evidence TEXT);
CREATE TABLE IF NOT EXISTS support_batches(chat TEXT,batch TEXT,case_id INTEGER,PRIMARY KEY(chat,batch));
CREATE INDEX IF NOT EXISTS support_open_chat ON support(chat,state);''')
    try:
        c.execute('BEGIN IMMEDIATE');yield c;c.commit()
    except Exception:c.rollback();raise
    finally:c.close()
def state(chat,changes=None):
    with database() as c:
        row=c.execute('SELECT data FROM conversations WHERE chat=?',(chat,)).fetchone();v=json.loads(row[0]) if row else {}
        if changes is not None:
            v.update(changes);c.execute('INSERT OR REPLACE INTO conversations VALUES(?,?)',(chat,json.dumps(v,ensure_ascii=False)))
        return v
def case_family(reason):
    """Agrupa consultas de una misma falla sin confundirla con un cobro."""
    r=norm(reason).strip()
    if r in ('enlace_pago','conectividad_para_pago','payment_review','pago_revision','comprobante','pago_pendiente_revision'):
        return 'pago'
    if r in ('connection_unverified','replacement_review','reposicion_incierta','asistencia','derivacion','iphone','acceso','vencimiento') or any(x in r for x in ('conexion','conectividad','reposicion','iphone')):
        return 'acceso'
    return r or 'asistencia'

def ticket(chat,batch,reason,detail=''):
    """Un caso abierto por cliente/familia; cada lote conserva su resultado."""
    batch=str(batch);detail=str(detail)[:2000];reason=str(reason)
    with database() as c:
        # La repetición de un lote nunca reabre un caso ya resuelto.
        prior=c.execute('SELECT case_id FROM support_batches WHERE chat=? AND batch=?',(chat,batch)).fetchone()
        if prior:return prior[0]
        prior=c.execute('SELECT id FROM support WHERE chat=? AND batch=?',(chat,batch)).fetchone()
        if prior:
            c.execute('INSERT INTO support_batches VALUES(?,?,?)',(chat,batch,prior[0]))
            return prior[0]
        family=case_family(reason);now=time.time()
        existing=next((x for x in c.execute("SELECT id,reason FROM support WHERE chat=? AND state IN ('open','ack') ORDER BY created,id",(chat,)) if case_family(x['reason'])==family),None)
        if existing:
            case_id=existing['id']
            c.execute('UPDATE support SET updated=? WHERE id=?',(now,case_id))
            c.execute('INSERT INTO support_events(case_id,at,action,evidence) VALUES(?,?,?,?)',(case_id,now,'consulta_agregada',json.dumps({'batch':batch,'reason':reason,'detail':detail},ensure_ascii=False)))
        else:
            cursor=c.execute('INSERT INTO support(chat,batch,reason,detail,state,created,updated) VALUES(?,?,?,?,?,?,?)',(chat,batch,reason,detail,'open',now,now))
            case_id=cursor.lastrowid
            c.execute('INSERT INTO support_events(case_id,at,action,evidence) VALUES(?,?,?,?)',(case_id,now,'creado',detail))
        c.execute('INSERT INTO support_batches VALUES(?,?,?)',(chat,batch,case_id))
        return case_id
def cases():
    with database() as c:return [dict(x) for x in c.execute("SELECT * FROM support WHERE state!='resolved' ORDER BY created LIMIT 200")]
def update_case(i,action,evidence=''):
    if action not in ('ack','resolve'):raise ValueError('accion_invalida')
    if action=='resolve' and len(evidence.strip())<12:raise ValueError('falta_evidencia_de_resolucion')
    with database() as c:
        if not c.execute('SELECT 1 FROM support WHERE id=?',(i,)).fetchone():raise ValueError('caso_inexistente')
        c.execute('UPDATE support SET state=?,updated=?,evidence=? WHERE id=?',('resolved' if action=='resolve' else 'ack',time.time(),evidence,i))
        c.execute('INSERT INTO support_events(case_id,at,action,evidence) VALUES(?,?,?,?)',(i,time.time(),action,evidence))
    return {'id':i,'state':'resolved' if action=='resolve' else 'ack'}
def menu(b):
    return 'Estos son los planes disponibles:\n'+'\n'.join(str(b.NOMBRES_PLAN.get(k,k))+': $'+str(v) for k,v in b.PRECIOS.items())+'\nDecime cuál querés y te paso su enlace de pago.'
def plan_for(text):
    t=norm(text)
    if re.search(r'mi plan|vence|vencimiento|mi codigo|recuperar|no funciona|no anda|no conecta',t):return None
    found=[]
    for k,pat in [('1h',r'\b(1\s*h(?:ora)?s?|una hora)\b'),('24h',r'\b(24\s*h(?:ora)?s?|un dia|diario)\b'),('7d',r'\b(7\s*dias?|una semana|semanal)\b'),('1mes',r'\b(1\s*mes|un mes|mensual|30\s*dias?)\b')]:
        if re.search(pat,t):found.append(k)
    return (found[0]+('_2' if re.search(r'\b(2|dos)\s*(equipos|dispositivos|celulares)',t) else '')) if len(found)==1 else None

def make_link(b,chat,plan,renew):
    from urllib.parse import urlparse
    if plan not in b.PRECIOS or plan not in b.DURACIONES:raise ValueError('plan_invalido')
    endpoint='/bot_renovar' if renew else '/crear_preferencia'
    with b.app.test_request_context(endpoint,method='POST',json={'chat_id':chat,'plan':plan}):
        result=b.app.view_functions[next(k for k,v in b.app.view_functions.items() if any(rule.rule==endpoint and rule.endpoint==k for rule in b.app.url_map.iter_rules()))]()
        status=result[1] if isinstance(result,tuple) else result.status_code
        response=result[0] if isinstance(result,tuple) else result
        d=response.get_json()
    if status!=200:raise ValueError('enlace_no_disponible')
    link=d.get('link') or d.get('init_point') or ''
    host=urlparse(link).hostname or ''
    if urlparse(link).scheme!='https' or not (host=='mpago.la' or host=='mercadopago.com.ar' or host.endswith('.mercadopago.com.ar')):raise ValueError('enlace_invalido')
    actual=plan
    if renew:
        mac=b._mac_de_chat(chat)
        actual=b._plan_renovacion(mac,plan) if mac else plan
    devices=2 if actual.endswith('_2') else 1
    if actual=='1mes' and callable(getattr(b,'_es_doble',None)) and b._es_doble(chat=chat):devices=2
    return {'plan':actual,'precio':d.get('precio',b.PRECIOS[actual]),'link':link,'at':time.time(),'renew':renew,'dispositivos':devices}

def quote(b,q):
    plan=q['plan'];duration=b.DURACIONES.get(plan)
    seconds=int(duration.total_seconds()) if hasattr(duration,'total_seconds') else None
    if seconds and seconds%86400==0:duration_text=str(seconds//86400)+' días'
    elif seconds and seconds%3600==0:duration_text=str(seconds//3600)+' horas'
    elif seconds and seconds%60==0:duration_text=str(seconds//60)+' minutos'
    else:duration_text=str(b.NOMBRES_PLAN.get(plan,plan))
    devices=q.get('dispositivos',2 if plan.endswith('_2') else 1)
    return (str(b.NOMBRES_PLAN.get(plan,plan))+' — $'+str(q['precio'])+
            '\nDuración del plan: '+duration_text+'. Dispositivos: '+str(devices)+
            (' (mismo vencimiento).' if devices==2 else '.')+'\n'+q['link']+
            '\nCuando el pago se apruebe, el sistema te enviará la confirmación correspondiente.')
def connectivity_claim(text):
    t=norm(text)
    action=r'(?:conectar(?:me)?|navegar)'
    if re.search(r'\b(?:no\s+(?:me\s+)?(?:puedo|logro|deja|permite)\s+|sin\s+poder\s+)'+action+r'\b',t):
        return True
    network=r'(?:internet|wi[\s-]*fi|conexion|servicio)'
    if re.search(r'\b(?:sin|no\s+(?:tengo|tenemos|hay))\s+(?:acceso\s+(?:a\s+|al\s+))?(?:el\s+|la\s+)?'+network+r'\b',t):
        return True
    failure=r'(?:no\s+(?:(?:me|nos|se)\s+)?(?:anda|funciona|conecta)|(?<!no )(?<!nunca )se\s+(?:(?:me|nos)\s+)?(?:cort[oa]|desconecta)|anda\s+mal)'
    before=r'\b'+failure+r'\s+(?:(?:el|la|mi|nuestro|nuestra)\s+)?'+network+r'\b'
    after=r'\b'+network+r'\s+'+failure+r'\b'
    return bool(re.search(before+'|'+after,t))

def commerce(b,chat,text,batch):
    t=norm(text);now=time.time();s=state(chat)
    paid_reported=bool(re.search(r'\b(?:pague|pagamos|pago\s+(?:hecho|realizado|aprobado)|(?<!no )(?<!sin )(?:esta|quedo)\s+pag(?:o|ado))\b',t))
    if re.search(r'(no tengo|sin|no hay|no me anda|no funciona).{0,25}(internet|conexion|datos)',t) and re.search(r'pagar|pago|mercado|link|enlace|transfer',t) and not paid_reported:
        return {'handled':True,'respuesta':'Para abrir el pago necesitás una conexión disponible. Si el portal de la red «Internet» te ofrece una prueba gratuita, podés usarla para pagar. Si no aparece, escribí «ayuda para pagar» y queda registrado para asistencia. No hace falta comprar otro código.'}
    if 'ayuda para pagar' in t:
        i=ticket(chat,batch,'conectividad_para_pago',text);return {'handled':True,'respuesta':f'Quedó registrada tu consulta #{i}: no podés abrir el pago por falta de conexión. Falta que el equipo técnico compruebe el acceso; todavía no está resuelto.'}
    if connectivity_claim(text):
        i=ticket(b.resolver_chat_id(chat),batch,'acceso_conexion',text)
        return {'handled':True,'respuesta':f'Quedó registrada tu consulta #{i} por la dificultad para conectarte. El equipo técnico debe revisar el acceso y el estado del servicio.'}
    plan=plan_for(text)
    renew=bool(re.search(r'\brenov',t)) and bool(b._mac_de_chat(chat))
    if not plan and renew:
        mac=b._mac_de_chat(chat);plan=b._plan_renovacion(mac,b._plan_de(mac) or '1mes')
    if not plan and t.strip(' .!¿?') in ('si','dale','ok','bueno','quiero','mandalo','enviamelo') and now-s.get('offered_at',0)<1800:plan=s.get('offered')
    if plan:
        if plan not in b.PRECIOS:return {'handled':True,'respuesta':menu(b)}
        state(chat,{'offered':plan,'offered_at':now})
        if re.search(r'cuanto|precio|cuesta|vale',t) and not re.search(r'quiero|comprar|pagar|mand|envi|link|enlace',t):
            return {'handled':True,'respuesta':str(b.NOMBRES_PLAN.get(plan,plan))+' cuesta $'+str(b.PRECIOS[plan])+'. ¿Te paso el enlace de pago?'}
        q=s.get('quote')
        # Una nueva solicitud explicita obtiene la tarifa efectiva actual.
        try:
            if not q or q.get('plan')!=plan or q.get('renew')!=renew or now-q.get('at',0)>900 or q.get('precio')!=b.PRECIOS.get(plan):q=make_link(b,chat,plan,renew)
            # Cotizaciones anteriores siguen siendo válidas; completar su
            # beneficio no requiere crear otro enlace de pago.
            if 'dispositivos' not in q:
                q=dict(q);q['dispositivos']=2 if q['plan'].endswith('_2') or (q['plan']=='1mes' and callable(getattr(b,'_es_doble',None)) and b._es_doble(chat=chat)) else 1
            state(chat,{'quote':q});return {'handled':True,'respuesta':quote(b,q)}
        except Exception:
            i=ticket(chat,batch,'enlace_pago',text);return {'handled':True,'respuesta':f'No pude obtener un enlace válido para ese plan. Quedó la consulta #{i} para revisión. No generé un código ni confirmé un pago.'}
    if re.search(r'no (me )?(anda|funciona|conecta|tengo internet)|sin internet|se corto',t):return {'handled':False}
    if re.search(r'\b(planes|precios|tarifas|wifi|wi fi)\b|\d+\s*(horas|dias|meses)',t):return {'handled':True,'respuesta':menu(b)}
    return {'handled':False}
def remember(b,d,result):
    chat=d.get('chat_id','');act=b._bot_active_lock.get(chat)
    if act and act.get('lock_id')==d.get('lock_id'):
        act['texto_lote']=d.get('texto','')
        if result.get('handled'):act['respuesta_verificada']=result.get('respuesta','')
        if not b._bot_guardar_estado():raise RuntimeError('persistencia')
    return result
def finalize(b,d):
    raw_chat=d.get('chat_id','');chat=b.resolver_chat_id(raw_chat);act=b._bot_active_lock.get(raw_chat,{})
    if act.get('respuesta_final'):return {'ok':True,'respuesta':act['respuesta_final']}
    text=act.get('texto_lote','');trusted=bool(act.get('respuesta_verificada'));answer=act.get('respuesta_verificada') or str(d.get('respuesta','')).strip()
    if not trusted:
        t=norm(answer)
        if d.get('accion') in ('derivar','reenviar_codigo') or re.search(r'revis|deriv|operador|te escrib|un ratito|resuelt|solucionad|equipo tecnico',t):
            i=ticket(chat,d.get('lock_id'),'asistencia',text);answer=f'Tu consulta quedó registrada con el número {i}. Falta comprobar la solución; todavía no está resuelta.'
        elif re.search(r'https?://|\d|\$|codigo|vence|vencimiento|pagad[oa]|cobrad[oa]|saldo|plan activo|acceso activo|conexion.{0,10}(activa|funciona)',t):answer=menu(b)
        answer=re.sub(r'(?i)^\s*(hola[,!. ]*)?(soy|somos) (el |un )?(bot|asistente)[^.\n]*[.\n]\s*','',answer)
        if len(answer)>950:answer=answer[:947].rsplit(' ',1)[0]+'…'
    if not answer:return {'ok':False,'error':'respuesta_vacia'}
    s=state(chat);now=time.time()
    if now-s.get('last_reply',0)>86400:answer='Hola, soy el asistente automático de SDeTecno. Te atiendo por mensajes.\n\n'+answer
    state(chat,{'last_reply':now})
    act['respuesta_final']=answer
    if not b._bot_guardar_estado():return {'ok':False,'error':'persistencia'}
    return {'ok':True,'respuesta':answer}
def init(b):
    from flask import request,jsonify
    from servicios_operativos import authorized
    b._bot_registrar_caso=lambda chat,batch,reason,text='':ticket(b.resolver_chat_id(chat),batch,reason,text)
    @b.app.route('/bot_respuesta_segura',methods=['POST'])
    def bot_respuesta_segura():
        d=request.get_json(silent=True) or {}
        with b._bot_lock:
            if not authorized(b,d):return jsonify({'ok':False,'error':'lock_invalido'}),409
            return jsonify(finalize(b,d))
    @b.app.route('/panel_api/operaciones/seguimiento',methods=['GET','POST'])
    def bot_seguimiento():
        if request.method=='GET':return jsonify({'ok':True,'casos':cases()})
        d=request.get_json(silent=True) or {}
        try:return jsonify({'ok':True,'caso':update_case(int(d['id']),d.get('accion','ack'),d.get('evidencia',''))})
        except (ValueError,KeyError) as e:return jsonify({'ok':False,'error':str(e)}),400
    @b.app.after_request
    def registrar_derivacion(response):
        if request.path=='/bot_derivar' and response.status_code==200:
            d=request.get_json(silent=True) or {};raw_chat=d.get('chat_id','');chat=b.resolver_chat_id(raw_chat);act=b._bot_active_lock.get(raw_chat,{})
            if chat:ticket(chat,act.get('lock_id') or 'derivado:'+str(int(time.time()//120)),'derivacion',d.get('texto') or act.get('texto_lote',''))
        return response
    for chat,x in list(b.panel.get('derivados',{}).items()):ticket(b.resolver_chat_id(chat),'derivado:'+str(x.get('ts')),'derivacion',x.get('texto',''))
