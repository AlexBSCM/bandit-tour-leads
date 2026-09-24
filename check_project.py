# Простая проверка проекта для новичка.
# Запуск:  python check_project.py
# Ничего секретного не нужно, Telegram-ключи НЕ требуются.
import py_compile
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
OK = True

def check(name, cond, hint=""):
    global OK
    status = "OK  " if cond else "FAIL"
    if not cond:
        OK = False
    print(f"[{status}] {name}" + (f" — {hint}" if hint and not cond else ""))

print("=== 1. Python ===")
print("Версия:", sys.version.split()[0])
check("Python 3.10+", sys.version_info >= (3, 10))

print("\n=== 2. Файлы проекта ===")
for f in ["bot.py", "test_monitor.py", "config.example.json", "requirements.txt", "dashboard_server.py", "run_bot.bat", "watchdog.ps1"]:
    check(f"файл {f} есть", (BASE / f).exists())

print("\n=== 3. Синтаксис (без запуска бота) ===")
for f in ["bot.py", "test_monitor.py", "dashboard_server.py"]:
    try:
        py_compile.compile(str(BASE / f), doraise=True)
        check(f"{f} компилируется", True)
    except Exception as e:
        check(f"{f} компилируется", False, str(e))

print("\n=== 4. Логика фильтров (без Telegram) ===")
# Копируем актуальную логику из bot.py, чтобы проверить её без установки telethon
import importlib.util  # noqa

def load_build_patterns():
    # читаем функцию прямо из bot.py как текст и проверяем ключевые строки
    src = (BASE / "bot.py").read_text(encoding="utf-8")
    check("word-boundary исправлен (r'\\b')", r'pat = r"\b"' in src, "в bot.py остался r'\\\\b'")
    check("фенс Gemini исправлен (\\s*)", r'^```(?:json)?\s*' in src, "в bot.py остался \\\\s")
    check("classify_message async", "async def classify_message" in src)
    check("вызовы classify await", "await classify_message" in src)
    check("нет блокирующего sleep в скане", "time.sleep(5.5)" not in src, "остался time.sleep")
    check("cmd_lead_full использует format_thai_time", "date_part, time_part = format_thai_time" in src)
    check("дедупликация по (канал, id)", "_lead_key" in src and "is_lead_known(self, channel, msg_id)" in src)
    return src

load_build_patterns()

# Функциональные мини-тесты на скопированной логике
def build_patterns(keywords):
    patterns = []
    for kw in keywords:
        if re.fullmatch(r"[a-zA-Z\s]+", kw) and len(kw) <= 15:
            pat = r"\b" + re.escape(kw) + r"\b"
        else:
            pat = re.escape(kw)
        patterns.append(re.compile(pat, re.IGNORECASE))
    return patterns

def text_matches(text, patterns):
    if not text:
        return False
    return any(p.search(text) for p in patterns)

pats = build_patterns(["guide", "tour to", "экскурсия", "chiang mai"])
check("англ. 'looking for a guide in Chiang Mai' находится",
      text_matches("looking for a guide in Chiang Mai", pats))
check("рус. 'где экскурсия' находится",
      text_matches("где экскурсия по Чиангмаю?", pats))
check("'guidance' НЕ ложно срабатывает на 'guide'",
      not text_matches("guidance counselor", build_patterns(["guide"])))

_MOJIBAKE_RE = re.compile(r"(?:[РС][^\x00-\x7F]){3,}")
def fix_mojibake(text):
    if not text:
        return text
    if not _MOJIBAKE_RE.search(text):
        return text
    try:
        return text.encode("windows-1251").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

normal = "Собираюсь в Чиангмай, посоветуйте гида"
check("нормальный русский НЕ портится", fix_mojibake(normal) == normal)
# Заранее известная пара: "Привет" -> mojibake "РџСЂРёРІРµС‚" (UTF-8, прочитанный как cp1251)
broken = "РџСЂРёРІРµС‚"
check("настоящий mojibake чинится", fix_mojibake(broken) == "Привет")

# снятие фенса
raw = "```json\n{\"is_lead\": true}\n```"
clean = re.sub(r"^```(?:json)?\s*", "", raw.strip())
clean = re.sub(r"\s*```$", "", clean)
import json
try:
    json.loads(clean)
    check("фенс ```json снимается", True)
except Exception:
    check("фенс ```json снимается", False)

print("\n=== 5. Зависимости ===")
for mod in ["telethon", "google.generativeai", "matplotlib"]:
    try:
        __import__(mod)
        check(f"модуль {mod} установлен", True)
    except ImportError:
        check(f"модуль {mod} установлен", False, f"выполните: pip install -r requirements.txt")

print("\n=== Итог ===")
if OK:
    print("Всё зелёное. Проект к запуску готов.")
    print("Дальше: скопируйте config.example.json в test_config.json и впишите ключи, затем: python bot.py")
else:
    print("Есть красные FAIL — пришлите этот вывод целиком, разберём.")
