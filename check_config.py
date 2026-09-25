"""Проверка test_config.json: JSON, токен бота, chat_id, ключ Gemini (без вывода секретов)."""
import json
import urllib.error
import urllib.request
from pathlib import Path

cfg = json.loads(Path("test_config.json").read_text(encoding="utf-8-sig"))
print("JSON: OK")
print("Поля:", ", ".join(sorted(cfg.keys())))

# 1. Telegram bot token -> getMe
try:
    url = "https://api.telegram.org/bot%s/getMe" % cfg["bot_token"]
    data = json.loads(urllib.request.urlopen(url, timeout=20).read().decode("utf-8"))
    if data.get("ok"):
        u = data["result"]
        print("BOT: OK -> @%s (id=%s, name=%s)" % (u.get("username"), u.get("id"), u.get("first_name")))
    else:
        print("BOT: FAIL", data)
except urllib.error.HTTPError as e:
    print("BOT: FAIL HTTP", e.code, e.read().decode()[:200])
except Exception as e:
    print("BOT: FAIL", type(e).__name__, e)

# 2. chat_id sanity
cid = str(cfg.get("notify_chat_id", ""))
print("notify_chat_id:", cid if cid.isdigit() else "НЕ ЧИСЛО: " + cid)

# 3. Gemini keys -> one model check (we already know 403/404, just confirm)
keys = cfg.get("gemini_api_keys") or [cfg.get("gemini_api_key")]
keys = [k for k in keys if k]
print("ключей Gemini: %d" % len(keys))
for i, key in enumerate(keys, 1):
    try:
        url = ("https://generativelanguage.googleapis.com/v1beta/models/%s"
               ":generateContent?key=%s") % (cfg.get("gemini_model", "gemini-2.5-flash-lite"), key)
        body = json.dumps({"contents": [{"parts": [{"text": "скажи ок"}]}]}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=45)
        print("GEMINI #%d: OK" % i)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8"))["error"]["message"][:150]
        except Exception:
            msg = "?"
        print("GEMINI #%d: FAIL %s -> %s" % (i, e.code, msg))
    except Exception as e:
        print("GEMINI #%d: FAIL %s -> %s" % (i, type(e).__name__, e))

# channels: prefer channels.json (tracked in git) over config
ch_file = Path("channels.json")
if ch_file.exists():
    try:
        _cj = json.loads(ch_file.read_text(encoding="utf-8-sig"))
        _ch = _cj.get("channels", _cj) if isinstance(_cj, dict) else _cj
        print("channels.json:", len(_ch), _ch)
    except Exception as e:
        print("channels.json: FAIL", e)
else:
    print("channels.json: отсутствует (каналы берутся из test_config.json)")
print("channels:", cfg.get("channels"))
