import sys, os, json, time, socket, sqlite3, subprocess, urllib.request, urllib.error, pathlib, threading, shutil
NL = chr(10)
if r"C:\dos_agentes_local\repos_referencia" not in sys.path:
    sys.path.insert(0, r"C:\dos_agentes_local\repos_referencia")
try:
    from token_saver_bridge import compress_text as _ts_compress
except Exception:
    _ts_compress = lambda x: x
DRIVE_ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG_DIR = pathlib.Path.home() / ".antigravity-agent"
CLOUD_DB = CFG_DIR / "cloud_accounts.db"
PUENTE_DB = pathlib.Path(r"C:\dos_agentes_local\estado_puente.db")
CFG_PATH = CFG_DIR / "gui_config.json"
TOKEN_FILE = CFG_DIR / "local_bridge_token"
MODELS = ["gemini-4-argon-high", "claude-sonnet-5-5-high", "claude-opus-5-5-high"]

def describe_error(exc):
    detail = str(exc)
    if isinstance(exc, urllib.error.HTTPError):
        detail += " | " + exc.read(4096).decode("utf-8", errors="replace")
    for path in (CFG_PATH, TOKEN_FILE):
        try:
            secret = (json.loads(path.read_text(encoding="utf-8")).get("proxy", {}).get("api_key", "")
                      if path == CFG_PATH else path.read_text(encoding="utf-8").strip())
            if secret: detail = detail.replace(secret, "[REDACTED]")
        except Exception: pass
    return " ".join(detail.split())[:1200]


def _is_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0): return True
    except Exception: return False

def ensure_services_running():
    py_bin = r"C:\dos_agentes_local\.venv\Scripts\python.exe"
    if not _is_port_open(8765):
        try:
            subprocess.Popen([py_bin, "-X", "utf8", r"C:\dos_agentes_local\auto_bridge_8765.py"], creationflags=0x00000008 | 0x08000000, close_fds=True)
            for _ in range(12):
                if _is_port_open(8765): break
                time.sleep(0.25)
        except Exception: pass

def detect_project_and_brain(custom_cwd=None):
    cwd = pathlib.Path(custom_cwd) if custom_cwd else pathlib.Path.cwd()
    proj_name = cwd.name.upper()
    con = sqlite3.connect(str(PUENTE_DB))
    row = con.execute("SELECT stack_rules, critical_paths FROM project_brain WHERE UPPER(project_name)=?", (proj_name,)).fetchone()
    con.close()
    if row: return proj_name, row[0], row[1], str(cwd)
    return proj_name, "Resolver dudas entre agentes sin preguntar a Silvano y entregar 100% terminado.", "db,auth,config", str(cwd)

def build_repo_snapshot(proj_dir: str) -> str:
    p = pathlib.Path(proj_dir)
    try:
        files = sorted([x.name + ("/" if x.is_dir() else "") for x in p.iterdir() if not x.name.startswith(".")])[:25]
    except Exception:
        files = []
    git_info = ""
    try:
        git_path = os.pathsep.join(x for x in os.environ.get("PATH", "").split(os.pathsep) if "shims" not in x.lower())
        git_bin = shutil.which("git.exe", path=git_path)
        if not git_bin: return f"[SNAPSHOT_REAL CWD={proj_dir} | items={files} | git=no disponible]"
        g = subprocess.run([git_bin, "--no-optional-locks", "status", "-s"], cwd=proj_dir, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        if g.returncode == 0 and g.stdout.strip():
            git_info = " | git_status: " + " ; ".join(g.stdout.strip().splitlines()[:10])
    except Exception: pass
    return f"[SNAPSHOT_REAL CWD={proj_dir} | items={files}{git_info}]"

def rotate_account():
    con = sqlite3.connect(str(CLOUD_DB))
    rows = con.execute("SELECT id, email FROM accounts WHERE status='active' ORDER BY COALESCE(last_used, 0) ASC").fetchall()
    if not rows: con.close(); return None, "none"
    cid, email = rows[0]
    con.execute("UPDATE accounts SET is_active = CASE WHEN id=? THEN 1 ELSE 0 END, last_used = CASE WHEN id=? THEN ? ELSE last_used END", (cid, cid, int(time.time()*1000)))
    con.commit(); con.close()
    return cid, email

def call_manager(prompt, model, acct_id):
    cfg = json.loads(CFG_PATH.read_text(encoding="utf-8")).get("proxy", {}) if CFG_PATH.exists() else {}
    url = f"http://{cfg.get('host','127.0.0.1')}:{cfg.get('port',8045)}/v1/chat/completions"
    payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Antigravity-Account-Id": str(acct_id or "")}
    if cfg.get("api_key"): headers["Authorization"] = f"Bearer {cfg['api_key']}"
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60 if model.startswith("gemini") else 22) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))["choices"][0]["message"]["content"].strip()

def call_bridge_8765(prompt):
    headers = {"Content-Type": "application/json"}
    if TOKEN_FILE.exists():
        headers["Authorization"] = "Bearer " + TOKEN_FILE.read_text(encoding="utf-8").strip()
    req = urllib.request.Request("http://127.0.0.1:8765/ask", data=json.dumps({"prompt": prompt}).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=115) as r:
        d = json.loads(r.read().decode("utf-8", errors="replace"))
        return (d.get("response") or d.get("text") or str(d)).strip()

def evaluate_factory(raw_prompt, custom_cwd=None, mode="work"):
    ensure_services_running()
    proj, brain_rules, _, proj_dir = detect_project_and_brain(custom_cwd)
    snap = build_repo_snapshot(proj_dir)
    # A compression heuristic must not discard pending requirements or evidence.
    clean_prompt = (raw_prompt if mode == "verify" else _ts_compress(raw_prompt)) + NL + snap
    high_triggers = ["drop table", "delete from", "rm -rf", "format ", "credenciales", "migracion destructiva"]
    risk = "ALTO" if any(k in clean_prompt.lower() for k in high_triggers) else "BAJO"
    results = {"ag_tag": "", "ag_ans": "", "br_ans": "", "ag_ok": False, "br_ok": False}
    acct_id, email = rotate_account()
    if mode == "decide":
        r8045 = "Toma la MEJOR decision tecnica/diseno AHORA MISMO en 2 lineas sin preguntarle a Silvano"
        r8765 = "Valida y confirma la decision en 2 lineas para avanzar sin frenar"
    elif mode == "verify":
        closure_rule = ("Compara el PEDIDO ORIGINAL completo con el resultado y la evidencia de CADA requisito. "
                        "Si falta el pedido original o evidencia suficiente, responde INCOMPLETO_FALTA. "
                        "Abrir una pagina o preparar un formulario no acredita enviarlo; exige confirmacion del sitio si se pidio envio. "
                        "Un paso intermedio no completa el objetivo. Si hay pendientes, no apruebes aunque otros pasos funcionen. "
                        "Un bloqueo real debe informarse como pendiente con su causa, nunca COMPLETO_100%. "
                        "El snapshot solo acredita nombres; no has leido archivos ni ejecutado pruebas. "
                        "Responde en UNA linea exactamente COMPLETO_100% o INCOMPLETO_FALTA: <requisito y evidencia que falta>.")
        r8045 = "Inspector de Cierre: " + closure_rule
        r8765 = "Auditor de Cierre: " + closure_rule
    else:
        r8045 = "Asesor Antigravity: propone una solucion concreta en maximo 5 lineas para que el ejecutor local la implemente. Esta llamada es solo inferencia: no lees archivos ni ejecutas comandos. El snapshot solo acredita nombres. Nunca presentes acciones propuestas ni pruebas inventadas como realizadas"
        r8765 = "Puente Auditor de Arquitectura y Decisiones: valida consistencia en max 3 lineas. Esta llamada es solo inferencia; no afirmes haber leido codigo o ejecutado pruebas sin evidencia adjunta"
    def w8045():
        p = f"[BRAIN {proj}: {brain_rules}]" + NL + f"[{r8045}]: {clean_prompt}"
        errors = []
        for m in MODELS:
            try:
                results["ag_ans"] = call_manager(p, m, acct_id)
                if not results["ag_ans"]: raise ValueError("respuesta vacia")
                results["ag_ok"] = True
                results["ag_tag"] = f"[ANTIGRAVITY:{email}:{m}]"
                return
            except Exception as e: errors.append(f"{m}: {describe_error(e)}")
        results["ag_tag"] = f"[ANTIGRAVITY:{email}:error]"
        results["ag_ans"] = "ERROR: " + " | ".join(errors)
    def w8765():
        p = f"[BRAIN {proj}: {brain_rules}]" + NL + f"[{r8765}]: {clean_prompt}"
        try:
            results["br_ans"] = call_bridge_8765(p)
            if not results["br_ans"]: raise ValueError("respuesta vacia")
            results["br_ok"] = True
        except Exception as e: results["br_ans"] = "ERROR: " + describe_error(e)
    t1 = threading.Thread(target=w8045, daemon=True); t2 = threading.Thread(target=w8765, daemon=True)
    deadline = time.monotonic() + 120
    t1.start(); t2.start()
    for t in (t1, t2): t.join(timeout=max(0, deadline-time.monotonic()))
    results = dict(results)
    if not results["ag_ans"]:
        results["ag_tag"] = "[ANTIGRAVITY:NO_DISPONIBLE:timeout]"
        results["ag_ans"] = "ERROR: plazo de auditoria agotado"
    if not results["br_ans"]: results["br_ans"] = "ERROR: plazo del puente agotado"
    try:
        con = sqlite3.connect(str(PUENTE_DB))
        con.execute("INSERT INTO factory_audit_log (project, account_used, sec_review, arch_review, risk_level) VALUES (?, ?, ?, ?, ?)", (proj, results["ag_tag"], results["ag_ans"][:4000], results["br_ans"][:4000], f"{mode.upper()}:{risk}"))
        con.commit(); con.close()
    except Exception: pass
    summary = f"[BRAIN:{proj}] [MODO:{mode.upper()}] [RIESGO:{risk}]" + NL + f"{results['ag_tag']}: {results['ag_ans']}" + NL + f"[PUENTE_8765]: {results['br_ans']}"
    transport_ok = bool(results["ag_ok"] and results["br_ok"])
    approved = transport_ok and all(results[key].strip() == "COMPLETO_100%" for key in ("ag_ans", "br_ans"))
    return {"project": proj, "risk": risk, "summary": summary, "ag_tag": results["ag_tag"],
            "transport_ok": transport_ok, "approved": approved,
            "ok": approved if mode == "verify" else transport_ok}

def main():
    args = sys.argv[1:]
    if "--exec" in args or "--exec-py" in args:
        try:
            import bridge_local_client
            flag = "--exec" if "--exec" in sys.argv else "--exec-py"
            sys.argv.remove(flag)
            sys.exit(bridge_local_client.main())
            return
        except Exception as e:
            print(f"ERROR_EXEC_LOCAL_CLIENT: {e}"); sys.exit(1)
    mode = "work"
    if "--decide" in args: mode = "decide"; args.remove("--decide")
    if "--verify" in args: mode = "verify"; args.remove("--verify")
    raw_prompt = " ".join([a for a in args if a not in ("--puente","--groq","--factory")]).strip() or sys.stdin.read().strip()
    if not raw_prompt: print("OK_FACTORY_READY"); return
    result = evaluate_factory(raw_prompt, mode=mode)
    print(result["summary"], flush=True)
    sys.exit(0 if result["ok"] else 1)

if __name__ == "__main__":
    main()
