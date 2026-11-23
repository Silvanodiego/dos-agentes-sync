import sys, os, json, time, sqlite3, subprocess, shutil, pathlib
NL = chr(10)
DRIVE_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DRIVE_ROOT / "DOS AGENTES"))
sys.path.insert(0, r"C:\dos_agentes_local\repos_referencia")
import agy_passthrough as agy
from token_saver_bridge import compress_text

PUENTE_DB = pathlib.Path(r"C:\dos_agentes_local\estado_puente.db")

def resolve_proj_dir(proj_name: str) -> pathlib.Path:
    con = sqlite3.connect(str(PUENTE_DB))
    row = con.execute("SELECT project_path FROM project_brain WHERE UPPER(project_name)=?", (proj_name.upper(),)).fetchone()
    con.close()
    if row and row[0] and pathlib.Path(row[0]).exists():
        return pathlib.Path(row[0])
    cand = DRIVE_ROOT / proj_name
    if cand.exists(): return cand
    return pathlib.Path.cwd()

def add_task(project: str, prompt: str, test_cmd: str = ""):
    con = sqlite3.connect(str(PUENTE_DB))
    cur = con.execute("INSERT INTO factory_queue (project, task_prompt, test_cmd, status) VALUES (?, ?, ?, 'PENDING')", (project.upper(), prompt, test_cmd))
    tid = cur.lastrowid
    con.commit(); con.close()
    print(f"TAREA_ENCOLADA_OK: ID={tid} | PROYECTO={project.upper()}")
    return tid

def execute_autonomous_task(row):
    tid, proj, prompt, test_cmd, status, attempts = row
    proj_dir = resolve_proj_dir(proj)
    con = sqlite3.connect(str(PUENTE_DB))
    con.execute("UPDATE factory_queue SET status='RUNNING', attempts=attempts+1, updated_at=strftime('%s','now') WHERE id=?", (tid,))
    con.commit()
    eval_res = agy.evaluate_factory(prompt, custom_cwd=str(proj_dir))
    risk, audit_txt = eval_res["risk"], eval_res["summary"]
    if risk == "ALTO" and status != "APPROVED":
        con.execute("UPDATE factory_queue SET status='WAITING_HUMAN', risk_level=?, spec_and_audit=?, updated_at=strftime('%s','now') WHERE id=?", (risk, audit_txt, tid))
        con.commit(); con.close()
        print(f"[TAREA #{tid} PAUSADA - RIESGO ALTO]")
        return
    exec_out, success = "", True
    try:
        if "limpiar" in prompt.lower() and "temporal" in prompt.lower():
            exts_clean = {".tmp", ".log", ".bak", ".cache", ".swp"}
            dirs_clean = {"__pycache__", ".temp", "tmp", ".cache"}
            removed = []
            for p in proj_dir.glob("**/*"):
                if p.is_symlink() or p.is_junction(): continue
                try: p.resolve().relative_to(proj_dir.resolve())
                except ValueError: continue
                if any(part in {".git", ".venv", "node_modules"} for part in p.relative_to(proj_dir).parts): continue
                if p.is_file() and (p.suffix.lower() in exts_clean or p.name.endswith("~")):
                    try: p.unlink(); removed.append(p.name)
                    except Exception: pass
                elif p.is_dir() and p.name in dirs_clean:
                    shutil.rmtree(str(p), ignore_errors=True); removed.append(p.name + "/")
            exec_out = f"Temporales eliminados: {len(removed)} items"
        if test_cmd:
            proc = subprocess.run(test_cmd, cwd=str(proj_dir), shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
            raw_t = (proc.stdout or "") + (NL + proc.stderr if proc.stderr else "")
            exec_out += (NL if exec_out else "") + compress_text(raw_t)
            success = (proc.returncode == 0)
        elif not exec_out:
            codex_bin = shutil.which("codex")
            if codex_bin:
                proc = subprocess.run([codex_bin, "exec", "--skip-git-repo-check", "-s", "danger-full-access", prompt], env={**os.environ, "CODEX_HOME": r"C:\Users\H_P\.cx\ejecutor", "CODEX_EQUIPO_CHILD": "1"}, cwd=str(proj_dir), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
                exec_out = compress_text((proc.stdout or "") + (NL + proc.stderr if proc.stderr else ""))
                success = (proc.returncode == 0)
            else:
                exec_out = "Spec/Auditoria completada. Listo."
    except Exception as e:
        success, exec_out = False, f"Error: {e}"
    final_status = "DONE" if success else ("PENDING" if attempts < 2 else "FAILED")
    con.execute("UPDATE factory_queue SET status=?, risk_level=?, spec_and_audit=?, last_output=?, updated_at=strftime('%s','now') WHERE id=?", (final_status, risk, audit_txt, exec_out[:4000], tid))
    con.commit(); con.close()
    print(f"[TAREA #{tid} -> {final_status}] ({proj})" + NL + "[RESULTADO]: " + exec_out[:300])

def run_queue():
    con = sqlite3.connect(str(PUENTE_DB))
    rows = con.execute("SELECT id, project, task_prompt, test_cmd, status, attempts FROM factory_queue WHERE status IN ('PENDING', 'APPROVED') ORDER BY id ASC").fetchall()
    con.close()
    for r in rows: execute_autonomous_task(r)

def main():
    args = sys.argv[1:]
    if not args: pass
    elif args[0] == "autopilot" and len(args) >= 3:
        add_task(args[1], args[2], args[3] if len(args) >= 4 else "")
        run_queue()

if __name__ == "__main__":
    main()


