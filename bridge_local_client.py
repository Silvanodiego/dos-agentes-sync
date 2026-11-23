import json,pathlib,sys,urllib.request,urllib.error
CFG=pathlib.Path.home()/".antigravity-agent"
def request(path,data):
    token=(CFG/"local_bridge_token").read_text(encoding="utf-8").strip()
    req=urllib.request.Request("http://127.0.0.1:8765"+path,data=json.dumps(data).encode("utf-8"),headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=95) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        return json.load(e)
def main():
    args=sys.argv[1:]
    try: result=request("/exec",{"task":args[0] if args else ""})
    except Exception as e: result={"status":"error","error":str(e)}
    print("[BRAIN:DOS AGENTES] [MODO:WORK] [RIESGO:NO_EVALUADO]")
    print("[ANTIGRAVITY:NO_INVOCADO:local]: ejecucion local; sin veredicto de modelo")
    print("[PUENTE_8765]: "+result.get("status","error")+" exit="+str(result.get("exit_code","N/A")))
    for k in ("stdout","stderr","error","detail"):
        if result.get(k): print(result[k].rstrip())
    return result.get("exit_code",0 if result.get("status")=="ok" else 1)
if __name__=="__main__": sys.exit(main())
