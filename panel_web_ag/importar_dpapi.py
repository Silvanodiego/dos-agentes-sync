import ctypes,base64,json,sqlite3,time,datetime
from pathlib import Path
root=Path.home();db=root/'.antigravity-agent/cloud_accounts.db'
bak=Path('C:/dos_agentes_local/backups')/('manager_'+str(int(time.time()))+'.db');bak.parent.mkdir(parents=True,exist_ok=True)
c=sqlite3.connect(db);b=sqlite3.connect(bak);c.backup(b);b.close()
class Blob(ctypes.Structure):
 _fields_=[('n',ctypes.c_ulong),('p',ctypes.POINTER(ctypes.c_ubyte))]
items=[]
for i in range(1,5):
 raw=(root/f'AppData/Local/agentes/antigravity-perfiles/cuenta-{i}/agy_credencial.dpapi').read_bytes();buf=ctypes.create_string_buffer(raw);a=Blob(len(raw),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)));o=Blob()
 if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(a),None,None,None,None,1,ctypes.byref(o)):raise ctypes.WinError()
 try:outer=json.loads(ctypes.string_at(o.p,o.n))
 finally:ctypes.windll.kernel32.LocalFree(o.p)
 d=json.loads(base64.b64decode(outer['blob']));t=d['token'];email=d['id_token_email'];t['expiry_timestamp']=int(datetime.datetime.fromisoformat(t['expiry'].replace('Z','+00:00')).timestamp());t['email']=email
 if not t.get('refresh_token'):raise RuntimeError('Missing refresh token')
 items.append((i,email,json.dumps(t)))
with c:
 for i,email,t in items:
  old=c.execute('select id from accounts where provider=? and email=?',('google',email)).fetchone();aid=old[0] if old else f'agy-cuenta-{i}'
  c.execute('insert into accounts(id,provider,email,name,token_json,created_at,last_used,status) values(?,?,?,?,?,?,?,?) on conflict(id) do update set token_json=excluded.token_json,name=excluded.name',(aid,'google',email,f'cuenta-{i}',t,int(time.time()),0,'active'))
c.close();print('IMPORTADAS: 4; backup:',bak)
