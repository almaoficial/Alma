import json, subprocess, sys, datetime, os
modelo = sys.argv[1]
msgs = json.dumps([{"role": "user", "content": "Respondé solo: OK"}])
t0 = datetime.datetime.now(datetime.timezone.utc)
try:
    r = subprocess.run(
        [sys.executable, os.path.expanduser("~/workspace/skills/openrouter/bin/or_chat.py"),
         "--model", modelo, "--messages", msgs,
         "--max-tokens", "16", "--temperature", "0", "--timeout", "90"],
        capture_output=True, text=True, timeout=150)
    out, err, rc = r.stdout.strip(), r.stderr.strip(), r.returncode
except subprocess.TimeoutExpired:
    out, err, rc = "", "TIMEOUT local 150s", -99
t1 = datetime.datetime.now(datetime.timezone.utc)
res = {"modelo": modelo, "utc_inicio": t0.isoformat(), "utc_fin": t1.isoformat(),
       "rc": rc, "stdout": out[:600], "stderr": err[:300]}
if rc == 0:
    try:
        txt = json.loads(out).get("text", "")
        res["texto"] = txt[:100]
        res["resultado"] = "responde" if txt.strip() else "responde_vacio"
    except Exception:
        res["resultado"] = "responde_sin_json"
elif "429" in out or "429" in err:
    res["resultado"] = "429"
else:
    res["resultado"] = "otro_error"
print(json.dumps(res, ensure_ascii=False))
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sondas.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps(res, ensure_ascii=False) + "\n")
