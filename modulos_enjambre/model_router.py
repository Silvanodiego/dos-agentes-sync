"""Cascada estricta, con enfriamiento persistente por cuenta y familia."""
import re
from contextlib import closing
import sqlite3
import time
from pathlib import Path
DB_PATH = str(Path(__file__).resolve().parent.parent / "memoria_reloj" / "estado_puente.db")
SONNET = ['claude-sonnet-5-5-high', 'claude-sonnet-5-5-medium']
OPUS = ['claude-opus-5-5-high', 'claude-opus-5-5-medium']
ARGON = ['gemini-4-argon-high']
ALLOWED_MODELS = SONNET + OPUS + ARGON
def family(model):
    return next((f for f in ('sonnet','opus','argon','flash') if f in model), model)
def stage(model):
    return {'sonnet':1,'opus':2,'argon':3,'flash':4}.get(family(model), 0)
def rank_models(catalog, prompt, tier='auto', metrics=None):
    enabled = {x['id'] for x in catalog if x.get('enabled',True)}
    order = [SONNET[0], OPUS[0], ARGON[0]]
    return 'cascada', [m for m in order if m in enabled]
def connection(path=None):
    con = sqlite3.connect(path or DB_PATH, timeout=30)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('CREATE TABLE IF NOT EXISTS cooldown_familias (cuenta TEXT, familia TEXT, cooldown_until REAL NOT NULL, detalle TEXT, actualizado REAL, PRIMARY KEY(cuenta,familia))')
    return con
def cooldowns(path=None):
    with closing(connection(path)) as con, con:
        return {(c,f):float(ts) for c,f,ts in con.execute('SELECT cuenta,familia,cooldown_until FROM cooldown_familias')}
def set_cooldown(account, model, seconds, detail, path=None):
    now=time.time()
    with closing(connection(path)) as con, con:
        con.execute('INSERT OR REPLACE INTO cooldown_familias VALUES (?,?,?,?,?)', (account,family(model),now+max(1,float(seconds)),detail,now))
def model_access_error(text):
    return bool(re.search(r'model[^\n]{0,100}(?:not found|not available|not supported|not authorized|access denied)|permission_denied|does not have access|AGY_ADC_AUTH|unsupported model|unknown model',text,re.I))
def model_not_found_error(text):
    return bool(re.search(r'(?:unknown|invalid|unsupported)\s+model|model[^\n]{0,100}(?:not found|not supported|does not exist|no admite)|modelo[^\n]{0,100}(?:inválido|no existe|no admitido)',text,re.I))


def claude_quota_exhausted(path=None):
    """Fail closed: all eight account/family pairs need live quota evidence."""
    import math
    try:
        with closing(sqlite3.connect('file:' + str(path or DB_PATH).replace('\\','/') + '?mode=ro', uri=True, timeout=3)) as con:
            records = {(c,f):(t,d) for c,f,t,d in con.execute('SELECT cuenta,familia,cooldown_until,detalle FROM cooldown_familias')}
        now = time.time()
        for n in range(1,5):
            for f in ('sonnet','opus'):
                ts, detail = records.get(('cuenta-'+str(n),f),(0,''))
                ts = float(ts)
                if not math.isfinite(ts) or ts <= now or model_access_error(str(detail)):
                    return False
                if not re.search(r'429|quota reached|rate.?limit|resource.exhausted', str(detail), re.I):
                    return False
        return True
    except (OSError, ValueError, TypeError, sqlite3.Error):
        return False
