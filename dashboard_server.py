"""BanditTour Lead Dashboard — простой веб-сервер без зависимостей.

Запуск:  python dashboard_server.py [port]
По умолчанию порт 8080 (его же показывает кнопка «Дашборд» в боте).
Данные читаются вживую из matches_found.json / scan_state.json,
ничего генерировать заранее не нужно.

Эндпоинты:
  /            — HTML-страница: статистика + таблица лидов
  /api/leads   — JSON со всеми лидами
  /api/stats   — JSON со статистикой
"""
import html
import json
import sys
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
LEADS_PATH = BASE_DIR / "matches_found.json"
STATE_PATH = BASE_DIR / "scan_state.json"
CONFIG_PATH = BASE_DIR / "test_config.json"

EMOJI = {"hot": "🔥", "warm": "🌤", "spam": "🗑", "noise": "❌"}


def load_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        pass
    return default


def get_stats(leads):
    cats = Counter((l.get("category") or "?") for l in leads)
    chans = Counter((l.get("channel_title") or l.get("channel") or "?") for l in leads)
    return {
        "total": len(leads),
        "by_category": dict(cats),
        "by_channel": dict(chans.most_common(20)),
    }


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>BanditTour — лиды</title>
<style>
body {{ font-family: sans-serif; max-width: 1000px; margin: 0 auto; padding: 16px; }}
.cards {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }}
.card {{ border: 1px solid #ccc; border-radius: 8px; padding: 8px 14px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; vertical-align: top; }}
th {{ background: #f5f5f5; }}
.text {{ max-width: 420px; white-space: pre-wrap; word-break: break-word; }}
.muted {{ color: #888; }}
</style>
</head>
<body>
<h1>🎯 BanditTour — лиды</h1>
<p class="muted">Обновлено: {updated} (автообновление раз в минуту) | Всего: {total}</p>
<div class="cards">{cards}</div>
<table>
<tr><th>Категория</th><th>Дата</th><th>Канал</th><th>Причина</th><th>Текст</th><th>Ссылка</th></tr>
{rows}
</table>
</body>
</html>"""


def render_page(leads):
    from datetime import datetime
    updated = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    stats = get_stats(leads)
    cards = [f'<div class="card"><b>Всего: {stats["total"]}</b></div>']
    for cat, n in sorted(stats["by_category"].items()):
        cards.append(f'<div class="card">{EMOJI.get(cat, "❓")} {html.escape(cat)}: <b>{n}</b></div>')
    if not leads:
        rows = '<tr><td colspan="6" class="muted">Лидов пока нет. Запустите бота (python bot.py) и дождитесь первых находок.</td></tr>'
    else:
        rows = []
        for l in leads[:200]:  # последние 200, файл уже отсортирован по дате
            cat = l.get("category", "?")
            date = (l.get("date") or "?")[:16].replace("T", " ")
            chan = html.escape(str(l.get("channel_title") or l.get("channel") or "?"))
            reason = html.escape(str(l.get("reason") or ""))
            text = html.escape(str(l.get("text") or ""))[:600]
            ch = str(l.get("channel") or "").lstrip("@")
            link = f"https://t.me/{ch}/{l.get('id')}" if ch and l.get("id") else ""
            link_html = f'<a href="{link}">открыть</a>' if link else '<span class="muted">—</span>'
            rows.append(
                f"<tr><td>{EMOJI.get(cat, '❓')} {html.escape(cat)}</td>"
                f"<td>{html.escape(date)}</td><td>{chan}</td>"
                f"<td>{reason}</td><td class=\"text\">{text}</td><td>{link_html}</td></tr>"
            )
        rows = "\n".join(rows)
    return PAGE_TEMPLATE.format(updated=updated, total=len(leads),
                                cards="".join(cards), rows=rows)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # тихие логи в консоль без лишнего шума
        sys.stderr.write("dashboard: " + fmt % args + "\n")

    def _send(self, body, content_type):
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        leads = load_json(LEADS_PATH, [])
        if not isinstance(leads, list):
            leads = [leads] if leads else []
        if path == "/api/leads":
            self._send(json.dumps(leads, ensure_ascii=False), "application/json")
        elif path == "/api/stats":
            state = load_json(STATE_PATH, {})
            stats = get_stats(leads)
            stats["channels_tracked"] = list(state.keys())
            self._send(json.dumps(stats, ensure_ascii=False), "application/json")
        elif path in ("/", "/index.html"):
            self._send(render_page(leads), "text/html")
        else:
            self.send_response(404)
            self.end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Dashboard: http://127.0.0.1:{port}  (Ctrl+C — остановить)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Остановлен.")


if __name__ == "__main__":
    main()
