"""Пробует несколько моделей Gemini, чтобы найти рабочую под текущий ключ."""
import json
import urllib.error
import urllib.request
from pathlib import Path

cfg = json.loads(Path("test_config.json").read_text(encoding="utf-8-sig"))
key = cfg["gemini_api_key"]
models = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.6-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-3.5-flash",
]
for m in models:
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (m, key)
    body = json.dumps({"contents": [{"parts": [{"text": "Ответь одним словом: ок"}]}]}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=45)
        data = json.loads(resp.read().decode("utf-8"))
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        print("%-28s OK -> %s" % (m, text.strip()[:40]))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8"))["error"]["message"][:110]
        except Exception:
            msg = "?"
        print("%-28s FAIL %s -> %s" % (m, e.code, msg))
    except Exception as e:
        print("%-28s FAIL %s" % (m, type(e).__name__))
