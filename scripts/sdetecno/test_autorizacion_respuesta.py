"""Exercise deployed response safeguards in isolation: no imports, DB writes or sends."""
import ast
import pathlib
import re
import sys
import time
import types
import unicodedata

backend = pathlib.Path(sys.argv[1])
source = backend.read_text(encoding='utf-8')
nodes = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name in ('norm', 'finalize')]
assert {n.name for n in nodes} == {'norm', 'finalize'}
records = []
states = {}
def state(chat, patch=None):
    value = states.setdefault(chat, {'last_reply': time.time()})
    if patch:
        value.update(patch)
    return value

def ticket(*args):
    records.append(args)
    return 123

scope = dict(re=re, time=time, unicodedata=unicodedata, state=state, ticket=ticket,
             menu=lambda _b: 'MENU_VERIFICADO')
exec(compile(ast.Module(body=nodes, type_ignores=[]), 'isolated-finalize', 'exec'), scope)

def run(answer, action='responder', trusted=''):
    records.clear()
    b = types.SimpleNamespace(resolver_chat_id=lambda c: c,
        _bot_active_lock={'isolated-test': {'texto_lote': 'consulta aislada', 'respuesta_verificada': trusted}},
        _bot_guardar_estado=lambda: True)
    result = scope['finalize'](b, {'chat_id': 'isolated-test', 'lock_id': 'isolated-lock',
                                  'respuesta': answer, 'accion': action})
    assert result['ok'] is True
    return result['respuesta'], len(records)

js = pathlib.Path(__file__).with_name('decidir_respuesta.js').read_text(encoding='utf-8')
fallback = re.search(r"respuesta = '([^']*No pude interpretar[^']*)';", js).group(1)
answer, count = run(fallback)
assert answer == fallback and count == 0
print('OK malformed-format fallback creates no support case')
answer, count = run('Necesito ayuda.', 'derivar')
assert '123' in answer and count == 1
print('OK explicit support request still registers a case')
answer, count = run('Codigo: 1234, precio $99.')
assert answer == 'MENU_VERIFICADO' and count == 0
print('OK unverified codes and prices still use verified menu')
answer, count = run('Untrusted response', trusted='Respuesta comercial verificada.')
assert answer == 'Respuesta comercial verificada.' and count == 0
print('OK trusted business response is preserved')
print('PASS 4 isolated authorization checks; no customer messages or DB writes.')
