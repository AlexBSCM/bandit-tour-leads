"""BanditTour Lead Dashboard — простой веб-сервер без зависимостей.

Запуск:  python dashboard_server.py [port]
По умолчанию порт 8080 (его же показывает кнопка «Дашборд» в боте).
Данные читаются вживую из matches_found.json / scan_state.json,
ничего генерировать заранее не нужно.

Статусы лидов (новый / прочитан / архив) хранятся отдельно в
lead_ui_state.json — бот этот файл не трогает, поэтому его отметки
не затираются при сохранении matches_found.json.

Эндпоинты:
  /                  — HTML-страница: статистика + фильтры + таблица лидов
  /api/leads         — JSON со всеми лидами
  /api/stats         — JSON со статистикой
  /api/lead-state    — GET: все статусы; POST {key,status}: сохранить статус
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
LEAD_UI_PATH = BASE_DIR / "lead_ui_state.json"

EMOJI = {"hot": "🔥", "warm": "🌤", "spam": "🗑", "noise": "❌"}
STATUSES = ("new", "read", "archived")
STATUS_TITLE = {"new": "Новые", "read": "Прочитанные", "archived": "Архив"}


def load_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        pass
    return default


def lead_key(lead):
    """Ключ статуса для лида: (канал, id) — совпадает с дедупликацией бота."""
    return "%s|%s" % (lead.get("channel") or "?", lead.get("id"))


def load_lead_state():
    data = load_json(LEAD_UI_PATH, {})
    return data if isinstance(data, dict) else {}


def save_lead_state(state):
    tmp = LEAD_UI_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(LEAD_UI_PATH)  # атомарная замена, чтобы не было обрыва записи


def get_stats(leads):
    cats = Counter((l.get("category") or "?") for l in leads)
    chans = Counter((l.get("channel_title") or l.get("channel") or "?") for l in leads)
    return {
        "total": len(leads),
        "by_category": dict(cats),
        "by_channel": dict(chans.most_common(20)),
    }


PAGE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>BanditTour — лиды</title>
<style>
body { font-family: sans-serif; max-width: 1000px; margin: 0 auto; padding: 16px; }
.cards { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.card { border: 1px solid #ccc; border-radius: 8px; padding: 8px 14px; }
.chips { display: flex; gap: 8px; flex-wrap: wrap; margin: 14px 0; }
.chip { border: 1px solid #ccc; background: #fff; border-radius: 999px; padding: 8px 14px;
        font-size: 14px; cursor: pointer; user-select: none; }
.chip b { display: inline-block; min-width: 18px; text-align: center; }
.chip.active { background: #1a73e8; color: #fff; border-color: #1a73e8; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { border: 1px solid #ddd; padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: #f5f5f5; white-space: nowrap; }
.text { max-width: 420px; white-space: pre-wrap; word-break: break-word; }
.muted { color: #888; }
.btn { border: 1px solid #ccc; background: #f8f8f8; border-radius: 8px; padding: 7px 11px;
       font-size: 13px; cursor: pointer; margin: 2px 4px 2px 0; }
.btn:active { transform: scale(.96); }
.btn.arch { background: #fff8e1; }
.btn.unarch, .btn.unread { background: #e8f5e9; }
td.acts { white-space: nowrap; }

/* видимость кнопок зависит от статуса строки */
tr[data-status="read"] .btn.read, tr[data-status="archived"] .btn.read { display: none; }
tr[data-status="new"] .btn.unread, tr[data-status="archived"] .btn.unread { display: none; }
tr[data-status="archived"] .btn.arch { display: none; }
tr[data-status="new"] .btn.unarch, tr[data-status="read"] .btn.unarch { display: none; }

/* --- планшет/маленький экран: таблица прокручивается по горизонтали --- */
@media (max-width: 900px) {
  .table-wrap { -webkit-overflow-scrolling: touch; }
  table { min-width: 860px; }
  .text { max-width: 300px; }
}

/* --- телефон: каждая строка = карточка с подписями полей --- */
@media (max-width: 640px) {
  body { padding: 10px; font-size: 15px; }
  h1 { font-size: 20px; margin: 8px 0; }
  .table-wrap { overflow-x: visible; }
  table, thead, tbody, tr, td { display: block; width: auto; min-width: 0; }
  thead { display: none; }
  table { min-width: 0; }
  tr { border: 1px solid #ccc; border-radius: 10px; margin-bottom: 12px;
       padding: 4px 10px; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  td { border: none; border-bottom: 1px solid #f0f0f0; padding: 8px 2px;
       white-space: normal; word-break: break-word; }
  td:last-child { border-bottom: none; }
  td::before { content: attr(data-label); display: block; font-size: 11px;
               letter-spacing: .04em; text-transform: uppercase; color: #999;
               font-weight: 700; margin-bottom: 2px; }
  td.text { max-width: none; font-size: 15px; line-height: 1.45; }
  td.acts { display: flex; flex-wrap: wrap; gap: 8px; padding: 10px 2px; }
  td.acts::before { width: 100%; }
  .btn { min-height: 42px; padding: 9px 14px; font-size: 14px; margin: 0; }
  .chip { padding: 10px 14px; font-size: 15px; }
}
</style>
</head>
<body>
<h1>🎯 BanditTour — лиды</h1>
<p class="muted">Обновлено: $updated (автообновление раз минуту) | Всего: $total</p>
<div class="cards">$cards</div>
<div class="chips">
  <button class="chip" data-f="new">📩 Новые <b id="c-new">$n_new</b></button>
  <button class="chip" data-f="read">👀 Прочитанные <b id="c-read">$n_read</b></button>
  <button class="chip" data-f="archived">📦 Архив <b id="c-arch">$n_arch</b></button>
  <button class="chip" data-f="all">🗂 Все <b id="c-all">$n_all</b></button>
</div>
<div class="table-wrap">
<table>
<thead><tr><th>Категория</th><th>Дата</th><th>Канал</th><th>Причина</th><th>Текст</th><th>Ссылка</th><th>Действия</th></tr></thead>
<tbody>
$rows
</tbody>
</table>
</div>
<script>
let state = $state_json;
let filter = localStorage.getItem('bt-filter') || 'new';

function rowStatus(tr) { return tr.getAttribute('data-status'); }

function recount() {
  const c = { all: 0, "new": 0, read: 0, archived: 0 };
  document.querySelectorAll('tr[data-key]').forEach(function (tr) {
    c.all++; const s = rowStatus(tr); if (c[s] !== undefined) c[s]++;
  });
  document.getElementById('c-new').textContent = c["new"];
  document.getElementById('c-read').textContent = c.read;
  document.getElementById('c-arch').textContent = c.archived;
  document.getElementById('c-all').textContent = c.all;
  return c;
}

function applyFilter() {
  let visible = 0;
  document.querySelectorAll('tr[data-key]').forEach(function (tr) {
    const show = (filter === 'all') || (rowStatus(tr) === filter);
    tr.style.display = show ? '' : 'none';
    if (show) visible++;
  });
  document.querySelectorAll('.chip').forEach(function (ch) {
    ch.classList.toggle('active', ch.getAttribute('data-f') === filter);
  });
  const ef = document.getElementById('empty-filter');
  if (ef) ef.style.display = (visible === 0) ? '' : 'none';
}

async function setStatus(btn, st) {
  const tr = btn.closest('tr');
  const key = tr.getAttribute('data-key');
  tr.setAttribute('data-status', st);
  if (st === 'new') { delete state[key]; } else { state[key] = st; }
  recount(); applyFilter();
  try {
    await fetch('/api/lead-state', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: key, status: st })
    });
  } catch (e) { console.log('save failed', e); }
}

document.querySelectorAll('.chip').forEach(function (ch) {
  ch.addEventListener('click', function () {
    filter = ch.getAttribute('data-f');
    try { localStorage.setItem('bt-filter', filter); } catch (e) {}
    applyFilter();
  });
});

recount(); applyFilter();
</script>
</body>
</html>"""


def render_page(leads):
    from datetime import datetime
    updated = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    stats = get_stats(leads)
    ui_state = load_lead_state()

    counts = {"new": 0, "read": 0, "archived": 0}
    for l in leads:
        st = ui_state.get(lead_key(l))
        if st in counts:
            counts[st] += 1

    cards = ['<div class="card"><b>Всего: %d</b></div>' % stats["total"]]
    for cat, n in sorted(stats["by_category"].items()):
        cards.append('<div class="card">%s %s: <b>%d</b></div>'
                     % (EMOJI.get(cat, "❓"), html.escape(cat), n))

    if not leads:
        rows = ('<tr><td colspan="7" class="muted">Лидов пока нет. Запустите бота '
                '(python bot.py) и дождитесь первых находок.</td></tr>')
    else:
        out = []
        for l in leads[:200]:  # последние 200, файл уже отсортирован по дате
            cat = l.get("category", "?")
            date = (l.get("date") or "?")[:16].replace("T", " ")
            chan = html.escape(str(l.get("channel_title") or l.get("channel") or "?"))
            reason = html.escape(str(l.get("reason") or ""))
            text = html.escape(str(l.get("text") or ""))[:600]
            ch = str(l.get("channel") or "").lstrip("@")
            link = "https://t.me/%s/%s" % (ch, l.get("id")) if ch and l.get("id") else ""
            link_html = '<a href="%s" target="_blank">открыть</a>' % link if link \
                else '<span class="muted">—</span>'
            st = ui_state.get(lead_key(l))
            st = st if st in STATUSES else "new"
            key = html.escape(lead_key(l), quote=True)
            out.append(
                '<tr data-key="%s" data-status="%s">'
                '<td data-label="Категория">%s %s</td>'
                '<td data-label="Дата">%s</td>'
                '<td data-label="Канал">%s</td>'
                '<td data-label="Причина">%s</td>'
                '<td data-label="Текст" class="text">%s</td>'
                '<td data-label="Ссылка">%s</td>'
                '<td data-label="Действия" class="acts">'
                '<button class="btn read" onclick="setStatus(this,\'read\')">✓ Прочитано</button>'
                '<button class="btn unread" onclick="setStatus(this,\'new\')">↩ В новые</button>'
                '<button class="btn arch" onclick="setStatus(this,\'archived\')">📦 В архив</button>'
                '<button class="btn unarch" onclick="setStatus(this,\'new\')">↩ Вернуть</button>'
                '</td></tr>'
                % (key, st, EMOJI.get(cat, "❓"), html.escape(cat),
                   html.escape(date), chan, reason, text, link_html)
            )
        out.append('<tr id="empty-filter" style="display:none">'
                   '<td colspan="7" class="muted">В этом разделе пока пусто.</td></tr>')
        rows = "\n".join(out)

    state_js = json.dumps(ui_state, ensure_ascii=False)
    page = PAGE_TEMPLATE
    for token, value in (
        ("$updated", updated),
        ("$total", str(len(leads))),
        ("$cards", "".join(cards)),
        ("$rows", rows),
        ("$n_new", str(counts["new"])),
        ("$n_read", str(counts["read"])),
        ("$n_arch", str(counts["archived"])),
        ("$n_all", str(len(leads))),
        ("$state_json", state_js),
    ):
        page = page.replace(token, value, 1)
    return page


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # тихие логи в файл, чтобы не зависеть от консоли
        # При запуске через pythonw (скрытый vbs-лаунчер) sys.stderr == None,
        # и запись в него роняла весь сервер на первом же запросе браузера.
        line = "dashboard: " + fmt % args + "\n"
        try:
            if getattr(sys, "stderr", None) is not None:
                sys.stderr.write(line)
                return
        except Exception:
            pass
        try:
            log_dir = BASE_DIR / "logs"
            log_dir.mkdir(exist_ok=True)
            with open(log_dir / "dashboard.log", "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    def _send(self, body, content_type, code=200):
        data = body.encode("utf-8")
        self.send_response(code)
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
        elif path == "/api/lead-state":
            self._send(json.dumps(load_lead_state(), ensure_ascii=False), "application/json")
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

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/lead-state":
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length > 0 else b""
            payload = json.loads(raw.decode("utf-8"))
            key = str(payload.get("key") or "")
            status = str(payload.get("status") or "")
            if not key or status not in STATUSES:
                raise ValueError("bad payload")
        except Exception:
            self._send(json.dumps({"ok": False, "error": "bad request"}),
                       "application/json", code=400)
            return
        state = load_lead_state()
        if status == "new":
            state.pop(key, None)  # «новый» — это состояние по умолчанию, не храним
        else:
            state[key] = status
        try:
            save_lead_state(state)
        except Exception as e:
            self._send(json.dumps({"ok": False, "error": str(e)[:100]}),
                       "application/json", code=500)
            return
        self._send(json.dumps({"ok": True, "key": key, "status": status}),
                   "application/json")


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
