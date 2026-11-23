import sys, json, urllib.request, pathlib

CHAT_URL = "https://gemini.google.com/app/ebb372bdb46e6358?hl=es_419"
CFG_PATH = pathlib.Path.home() / ".antigravity-agent" / "gui_config.json"

def main():
    prompt = " ".join(sys.argv[1:]).strip() or sys.stdin.read().strip()
    if not prompt:
        print("OK_CONSULTAR_GEMINI_READY")
        return
    cfg = json.loads(CFG_PATH.read_text(encoding="utf-8")).get("proxy", {}) if CFG_PATH.exists() else {}
    host, port, key = cfg.get("host", "127.0.0.1"), cfg.get("port", 8045), cfg.get("api_key", "")
    url = f"http://{host}:{port}/v1/chat/completions"
    payload = json.dumps({"model": "gemini-4-argon-high", "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=85) as r:
        data = json.loads(r.read().decode("utf-8"))
        print(data["choices"][0]["message"]["content"])

if __name__ == "__main__":
    main()
