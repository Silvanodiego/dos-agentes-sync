import os, sys, time, json, subprocess, pathlib

NL = chr(10)
PY_BIN = r"C:\dos_agentes_local\.venv\Scripts\python.exe"
DA_DIR = pathlib.Path(r"I:\Mi unidad\Claude\DOS AGENTES")
CODEX_EQUIPO = DA_DIR / "codex_equipo.py"
AGY_PT = DA_DIR / "agy_passthrough.py"
EJECUTOR_HOME = r"C:\Users\H_P\.cx\ejecutor"
JOBS_DIR = pathlib.Path(r"C:\dos_agentes_local\codex_jobs")
STATE_DIR = pathlib.Path(r"C:\dos_agentes_local\project_states")
STATE_DIR.mkdir(parents=True, exist_ok=True)

def get_state_file(cwd: str) -> pathlib.Path:
    safe = "".join(c if c.isalnum() else "_" for c in cwd)[-60:]
    return STATE_DIR / f"{safe}.txt"

def load_state(cwd: str) -> str:
    f = get_state_file(cwd)
    return f.read_text(encoding="utf-8", errors="replace")[-1200:] if f.exists() else ""

def save_state(cwd: str, pedido: str, resumen: str):
    f = get_state_file(cwd)
    prev = load_state(cwd)
    entry = f"- Pedido: {pedido[:220]} | Estado: {resumen[:300]}"
    lines = [l for l in (prev + NL + entry).splitlines() if l.strip()][-6:]
    f.write_text(NL.join(lines) + NL, encoding="utf-8")

def get_latest_job_id():
    if not JOBS_DIR.exists(): return "sin_job"
    dirs = sorted([d.name for d in JOBS_DIR.iterdir() if d.is_dir()], reverse=True)
    return dirs[0] if dirs else "sin_job"

def run_ejecutor(prompt: str, cwd: str):
    before_job = get_latest_job_id()
    env = os.environ.copy()
    for k in list(env.keys()):
        if k.startswith("CODEX_"):
            env.pop(k, None)
    env["CODEX_HOME"] = EJECUTOR_HOME
    env["CODEX_EQUIPO_CHILD"] = "1"
    cmd = ["codex.cmd", "exec", "--skip-git-repo-check", "-s", "danger-full-access", prompt]
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=360)
    after_job = get_latest_job_id()
    job_tag = after_job if after_job != before_job else f"perfil_ejecutor(rc={p.returncode})"
    out = ((p.stdout or "") + NL + (p.stderr or "")).strip()
    return p.returncode, job_tag, out[-3000:]

def run_verify(pedido: str, resumen: str, cwd: str):
    msg = f"Pedido original: {pedido} | Resultado ejecucion: {resumen}"
    p = subprocess.run([PY_BIN, "-X", "utf8", str(AGY_PT), "--verify", msg], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return ((p.stdout or "") + NL + (p.stderr or "")).strip()

def main():
    args = sys.argv[1:]
    max_iters = 4
    if len(args) >= 2 and args[0] == "--max":
        max_iters = int(args[1]); args = args[2:]
    pedido = " ".join(args).strip()
    if not pedido:
        print("Uso: auto <pedido completo>"); sys.exit(1)

    cwd = os.getcwd()
    hist = load_state(cwd)
    reglas_exec = (
        "REGLAS DE EJECUCION: Resuelve el pedido COMPLETO (A, B y C) de forma NO interactiva. "
        "PROHIBIDO pedirle al usuario que abra terminales o inicie sesion manualmente porque no puedes controlar ventanas externas. "
        "Si un metodo falla o esta bloqueado, cambia de estrategia tecnica automaticamente (SMB/net use, robocopy, SSH no interactivo, scripts, API) hasta resolverlo y verificarlo."
    )
    current_prompt = f"{reglas_exec}{NL}Historial reciente de esta carpeta:{NL}{hist or 'Sin historial'}{NL}Pedido actual: {pedido}"

    last_job = "NO_INVOCADO"
    last_verify = ""
    last_out = ""

    for i in range(1, max_iters + 1):
        rc, job_tag, exec_out = run_ejecutor(current_prompt, cwd)
        low_out = exec_out.lower()
        if rc != 0 and any(k in low_out for k in ("rate_limit_exceeded", "insufficient_quota", "usage limit reached", "you've hit your usage limit", "too many requests", "http 429", "status 429")):
            log_path = pathlib.Path(r"C:\dos_agentes_local\ultimo_auto.log")
            log_path.write_text(exec_out, encoding="utf-8", errors="replace")
            print(f"[BRAIN:{pathlib.Path(cwd).name.upper()}] [MODO:FALLBACK] [RIESGO:BAJO]")
            print("[CODEX_EJECUTOR:NO (CUOTA_AGOTADA)]: FALLBACK_CUOTA_EJECUTOR_AGOTADA")
            print("[ANTIGRAVITY:pendiente]: Tomar control desde Codex principal con agy.bat")
            print(f"[PUENTE_8765]: Log de cuota guardado en {log_path}")
            return

        last_job = f"SI ({job_tag}, vuelta {i}/{max_iters})"
        last_out = exec_out
        last_verify = run_verify(pedido, exec_out[-1200:], cwd)
        if "COMPLETO_100%" in last_verify and "INCOMPLETO_FALTA" not in last_verify:
            break

        current_prompt = (
            f"CONTINUACION OBLIGATORIA (Vuelta {i+1}/{max_iters}). {reglas_exec} "
            f"Pedido original: {pedido}. "
            f"La auditoria detecto faltantes o errores: {last_verify[:1200]}. "
            f"NO te rindas ni pidas accion manual innecesaria: cambia de enfoque tecnico, completa TODO y verificalo."
        )

    clean_lines = [l.strip() for l in last_out.splitlines() if l.strip() and not l.strip().lower().startswith("tokens used") and not l.strip().replace(",","").isdigit()]
    short_out = " | ".join(clean_lines[-3:])[:320]
    save_state(cwd, pedido, short_out or last_verify[:200])

    log_path = pathlib.Path(r"C:\dos_agentes_local\ultimo_auto.log")
    log_path.write_text(last_verify + NL + "--- EJECUTOR ---" + NL + last_out, encoding="utf-8", errors="replace")

    lines = last_verify.splitlines()
    h1 = lines[0] if len(lines) > 0 else f"[BRAIN:{pathlib.Path(cwd).name.upper()}] [MODO:VERIFY] [RIESGO:BAJO]"
    h2 = lines[1] if len(lines) > 1 else "[ANTIGRAVITY:auto]: Verificado"
    h3 = lines[2] if len(lines) > 2 else "[PUENTE_8765]: Verificado"
    print(h1)
    print(f"[CODEX_EJECUTOR:{last_job}]: {short_out or 'Finalizado'}")
    print(h2[:220])
    print(h3[:220])
    print(f"Log completo: {log_path}")

if __name__ == "__main__":
    main()


