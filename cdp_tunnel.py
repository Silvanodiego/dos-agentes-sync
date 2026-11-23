import subprocess,time,socket,sys,os
from pathlib import Path
ROOT=Path(r"C:\dos_agentes_local")
def listening():
 try:
  with socket.create_connection(("127.0.0.1",9222),2): return True
 except OSError: return False
def main():
 import msvcrt
 lock=open(ROOT/"cdp_tunnel.lock","a+b");lock.seek(0);lock.write(b"0");lock.flush();lock.seek(0)
 try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
 except OSError: return
 while True:
  try:
   if listening(): time.sleep(30);continue
   remote='printf %s IyEvYmluL3NoCnBpZD0kKGRvY2tlciBpbnNwZWN0IC1mICd7ey5TdGF0ZS5QaWR9fScgcGF0aXRhcy1nZW1pbmktYnJvd3NlcikKZXhlYyBuc2VudGVyIC10ICIkcGlkIiAtbiAvdXNyL2Jpbi9zb2NhdCBTVERJTyBUQ1A6MTI3LjAuMC4xOjkyMjIK | base64 -d > /tmp/patitas-cdp-connect.sh; chmod 700 /tmp/patitas-cdp-connect.sh; if ! curl -fsS --max-time 3 http://127.0.0.1:9222/json/version >/dev/null; then nohup socat TCP-LISTEN:9222,bind=127.0.0.1,reuseaddr,fork EXEC:/tmp/patitas-cdp-connect.sh >/tmp/patitas-cdp-relay.log 2>&1 </dev/null & fi'
   subprocess.run(["ssh","-o","BatchMode=yes","-o","ConnectTimeout=10","patitas-vps",remote],timeout=20,creationflags=0x08000000,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   subprocess.run(["ssh","-N","-o","BatchMode=yes","-o","ExitOnForwardFailure=yes","-o","ServerAliveInterval=30","-o","ServerAliveCountMax=3","-L","127.0.0.1:9222:127.0.0.1:9222","patitas-vps"],creationflags=0x08000000,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  except Exception as e:
   with open(ROOT/"cdp_tunnel.log","a",encoding="utf-8") as log: log.write(str(e)+"\n")
  time.sleep(10)
if __name__=="__main__": main()
