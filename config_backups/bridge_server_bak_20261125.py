import json, pathlib, subprocess, sys, hmac, time, sqlite3, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
CFG = pathlib.Path.home() / ".antigravity-agent"
CLOUD_DB = CFG / "cloud_accounts.db"
TOKEN_FILE = CFG / "local_bridge_token"
MODELS = ["gemini-4-argon-high", "claude-sonnet-5-5-high", "claude-opus-5-5-high"]

def get_token():
    return TOKEN_FILE.read_text(encoding="utf-8").strip() if TOKEN_FILE.exists() else ""

def pick_account():
    try:
        con = sqlite3.connect(str(CLOUD_DB))
        rows = con.execute("SELECT id, email FROM accounts WHERE status='active' ORDER BY COALESCE(last_used, 0) DESC").fetchall()
        con.close()
        return rows[0] if rows else (None, "default")
    except Exception:
        return (None, "default")

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, data):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        self.send(200, {"status": "ready", "port": 8765, "authenticated_execution": True, "version": 3})
    def do_POST(self):
        tok = get_token()
        if not tok or not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + tok):
            self.send(401, {"status": "error", "error": "unauthorized"}); return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n < 0 or n > 131072: raise ValueError("request too large")
            data = json.loads(self.rfile.read(n).decode("utf-8", errors="replace"))
            if self.path == "/exec":
                tasks = json.loads((CFG / "local_bridge_tasks.json").read_text(encoding="utf-8"))
                task = tasks.get(data.get("task"))
                if not task:
                    self.send(403, {"status": "error", "error": "task_not_registered"}); return
                p = subprocess.run(task["argv"], cwd=task["cwd"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=min(int(task.get("timeout", 30)), 90), shell=False, creationflags=0x08000000)
                self.send(200, {"status": "ok" if p.returncode == 0 else "error", "exit_code": p.returncode, "stdout": p.stdout[-65536:], "stderr": p.stderr[-65536:]})
            elif self.path == "/ask":
                c = json.loads((CFG / "gui_config.json").read_text(encoding="utf-8")).get("proxy", {})
                acct_id, acct_email = pick_account()
                url = "http://%s:%s/v1/chat/completions" % (c.get("host", "127.0.0.1"), c.get("port", 8045))
                last_err = "ningun modelo respondio"
                for m in MODELS:
                    try:
                        payload = json.dumps({"model": m, "messages": [{"role": "user", "content": str(data["prompt"])}]}).encode("utf-8")
                        headers = {"Content-Type": "application/json", "X-Antigravity-Account-Id": str(acct_id or "")}
                        if c.get("api_key"): headers["Authorization"] = "Bearer " + c["api_key"]
                        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                        with urllib.request.urlopen(req, timeout=60 if m.startswith("gemini") else 22) as r:
                            ans = json.loads(r.read().decode("utf-8", errors="replace"))["choices"][0]["message"]["content"].strip()
                        if ans:
                            self.send(200, {"status": "ok", "model": m, "account": acct_email, "response": ans})
                            return
                    except Exception as ex:
                        last_err = f"{m}: {ex}"
                self.send(502, {"status": "error", "error": "all_models_failed", "detail": last_err[:400]})
            else:
                self.send(404, {"status": "error", "error": "not_found"})
        except subprocess.TimeoutExpired:
            self.send(504, {"status": "error", "error": "task_timeout"})
        except Exception as e:
            self.send(502, {"status": "error", "error": type(e).__name__, "detail": str(e)[:400]})

if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()
