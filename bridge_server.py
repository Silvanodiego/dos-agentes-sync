import json, pathlib, subprocess, sys, hmac, time, sqlite3, urllib.request, urllib.error, socket
from datetime import datetime
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
CFG = pathlib.Path.home() / ".antigravity-agent"
CLOUD_DB = CFG / "cloud_accounts.db"
TOKEN_FILE = CFG / "local_bridge_token"
MODELS = ["gemini-4-argon-high", "claude-sonnet-5-5-high", "claude-opus-5-5-high"]

def get_token():
    return TOKEN_FILE.read_text(encoding="utf-8").strip() if TOKEN_FILE.exists() else ""

REQUEST_BUDGET = 110
ATTEMPT_TIMEOUT = 25

def active_accounts():
    # Solo metadatos: no se leen token_json ni otros secretos de cuentas.
    with closing(sqlite3.connect(CLOUD_DB.as_uri() + "?mode=ro", uri=True, timeout=2)) as con:
        rows = con.execute("SELECT id, email FROM accounts WHERE status='active' "
                           "ORDER BY COALESCE(is_active, 0) DESC, COALESCE(last_used, 0) DESC LIMIT 4").fetchall()
    return rows or [(None, "default")]

def pick_account():
    return active_accounts()[0]

def rotation_log(account, reason, next_account=None):
    # Numeros de posicion; nunca emails, prompts, cabeceras ni cuerpos de error.
    path = pathlib.Path(__file__).resolve().parent / "logs" / "bridge_8765.log"
    path.parent.mkdir(exist_ok=True)
    line = (f"{datetime.now().astimezone().isoformat(timespec='seconds')} "
            f"account={account} reason={reason} next_account={next_account or 'none'}\n")
    with path.open("a", encoding="utf-8") as log:
        log.write(line)

def ask_accounts(config, prompt):
    accounts = active_accounts()
    deadline = time.monotonic() + REQUEST_BUDGET
    url = "http://%s:%s/v1/chat/completions" % (config.get("host", "127.0.0.1"), config.get("port", 8045))
    last_error = "no_response"
    for index, (account_id, account_email) in enumerate(accounts, 1):
        reason = "models_exhausted"
        for model in MODELS:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                rotation_log(index, "request_deadline")
                return 502, {"status": "error", "error": "all_models_failed", "detail": "request_deadline"}
            payload = json.dumps({"model": model, "messages": [{"role": "user", "content": str(prompt)}]}).encode("utf-8")
            headers = {"Content-Type": "application/json", "X-Antigravity-Account-Id": str(account_id or "")}
            if config.get("api_key"):
                headers["Authorization"] = "Bearer " + config["api_key"]
            request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=min(ATTEMPT_TIMEOUT, remaining)) as response:
                    answer = json.loads(response.read().decode("utf-8", errors="replace"))["choices"][0]["message"]["content"].strip()
                if answer:
                    return 200, {"status": "ok", "model": model, "account": account_email, "response": answer}
                reason = "empty_response"
            except urllib.error.HTTPError as exc:
                reason = f"http_{exc.code}"
                exc.close()
                if exc.code == 429 or 500 <= exc.code <= 599:
                    break  # La siguiente cuenta prueba primero el modelo prioritario.
            except (TimeoutError, socket.timeout):
                reason = "timeout"
                break
            except urllib.error.URLError as exc:
                reason = "timeout" if isinstance(exc.reason, (TimeoutError, socket.timeout)) else "connection_error"
                break
            except (ValueError, KeyError, IndexError, TypeError):
                reason = "invalid_response"
            last_error = reason
        last_error = reason
        rotation_log(index, reason, index + 1 if index < len(accounts) else None)
    return 502, {"status": "error", "error": "all_models_failed", "detail": last_error}

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
                code, result = ask_accounts(c, data["prompt"])
                self.send(code, result)
            else:
                self.send(404, {"status": "error", "error": "not_found"})
        except subprocess.TimeoutExpired:
            self.send(504, {"status": "error", "error": "task_timeout"})
        except Exception as e:
            self.send(502, {"status": "error", "error": type(e).__name__, "detail": str(e)[:400]})

if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()
