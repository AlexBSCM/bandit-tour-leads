"""
SQLite-хранилище лидов для BanditTour.
Заменяет matches_found.json — быстрее, атомарнее, масштабируется до 100к+ записей.
Схема:
  leads(id, date, text, sender_id, channel, channel_title, category, reason, classified_at, text_hash, created_at)
  индексы: (channel, id) уникальный, (text_hash), (category), (date)
"""
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from common import BASE_DIR, normalize_text_hash, _lead_key

DB_PATH = BASE_DIR / "leads.db"
SCHEMA_VERSION = 1

_thread_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    if not hasattr(_thread_local, "conn") or _thread_local.conn is None:
        _thread_local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _thread_local.conn.row_factory = sqlite3.Row
        _thread_local.conn.execute("PRAGMA journal_mode=WAL")
        _thread_local.conn.execute("PRAGMA busy_timeout=5000")
        _thread_local.conn.execute("PRAGMA synchronous=NORMAL")
    return _thread_local.conn


@contextmanager
def _tx():
    conn = _get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db():
    """Создаёт таблицы и индексы, мигрирует данные из matches_found.json при первом запуске."""
    with _tx() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER NOT NULL,
                channel TEXT NOT NULL,
                date TEXT,
                text TEXT,
                sender_id INTEGER,
                channel_title TEXT,
                category TEXT,
                reason TEXT,
                classified_at TEXT,
                text_hash TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (channel, id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_text_hash ON leads(text_hash)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_category ON leads(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_date ON leads(date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_channel ON leads(channel)")

        # миграция из JSON, если БД пуста
        cur = conn.execute("SELECT COUNT(*) FROM leads")
        if cur.fetchone()[0] == 0:
            _migrate_from_json(conn)


def _migrate_from_json(conn: sqlite3.Connection):
    """Одноразовая миграция matches_found.json -> SQLite."""
    from bot import OUTPUT_PATH
    if not OUTPUT_PATH.exists():
        return
    try:
        data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            return
        for lead in data:
            h = lead.get("text_hash") or normalize_text_hash(lead.get("text", ""))
            conn.execute("""
                INSERT OR IGNORE INTO leads
                (id, channel, date, text, sender_id, channel_title, category, reason, classified_at, text_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lead.get("id"),
                lead.get("channel") or "?",
                lead.get("date"),
                lead.get("text"),
                lead.get("sender_id"),
                lead.get("channel_title"),
                lead.get("category"),
                lead.get("reason"),
                lead.get("classified_at"),
                h,
            ))
        print(f"Migrated {len(data)} leads from JSON to SQLite")
    except Exception as e:
        print(f"Migration failed: {e}")


def load_all_leads(limit: int = 200) -> list[dict]:
    """Возвращает последние N лидов (для дашборда/бота)."""
    with _tx() as conn:
        cur = conn.execute("""
            SELECT id, channel, date, text, sender_id, channel_title, category, reason, classified_at, text_hash
            FROM leads
            ORDER BY date DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cur.fetchall()]


def load_all_leads_full() -> list[dict]:
    """Все лиды — для бэкапа/экспорта."""
    with _tx() as conn:
        cur = conn.execute("""
            SELECT id, channel, date, text, sender_id, channel_title, category, reason, classified_at, text_hash
            FROM leads
            ORDER BY date DESC
        """)
        return [dict(row) for row in cur.fetchall()]


def lead_exists(channel: str, msg_id: int) -> bool:
    with _tx() as conn:
        cur = conn.execute("SELECT 1 FROM leads WHERE channel=? AND id=?", (channel, msg_id))
        return cur.fetchone() is not None


def text_hash_exists(text_hash: str) -> bool:
    if not text_hash:
        return False
    with _tx() as conn:
        cur = conn.execute("SELECT 1 FROM leads WHERE text_hash=?", (text_hash,))
        return cur.fetchone() is not None


def add_lead(lead: dict) -> bool:
    """Добавляет лид. Возвращает True если вставлен, False если дубль по (channel, id)."""
    h = lead.get("text_hash") or normalize_text_hash(lead.get("text", ""))
    lead["text_hash"] = h
    with _tx() as conn:
        try:
            conn.execute("""
                INSERT INTO leads
                (id, channel, date, text, sender_id, channel_title, category, reason, classified_at, text_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                lead.get("id"),
                lead.get("channel") or "?",
                lead.get("date"),
                lead.get("text"),
                lead.get("sender_id"),
                lead.get("channel_title"),
                lead.get("category"),
                lead.get("reason"),
                lead.get("classified_at"),
                h,
            ))
            return True
        except sqlite3.IntegrityError:
            return False


def get_stats() -> dict:
    with _tx() as conn:
        total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        by_cat = dict(conn.execute("SELECT category, COUNT(*) FROM leads GROUP BY category").fetchall())
        by_ch = dict(conn.execute("SELECT channel_title, COUNT(*) FROM leads GROUP BY channel_title ORDER BY COUNT(*) DESC LIMIT 20").fetchall())
        return {"total": total, "by_category": by_cat, "by_channel": by_ch}


def get_days_stats(days: int = 14) -> list[tuple[str, int]]:
    with _tx() as conn:
        cur = conn.execute("""
            SELECT substr(date, 1, 10) as day, COUNT(*)
            FROM leads
            WHERE date IS NOT NULL
            GROUP BY day
            ORDER BY day DESC
            LIMIT ?
        """, (days,))
        return [(row[0], row[1]) for row in cur.fetchall()]


def get_channels_stats() -> list[tuple[str, int]]:
    with _tx() as conn:
        cur = conn.execute("""
            SELECT channel_title, COUNT(*)
            FROM leads
            GROUP BY channel_title
            ORDER BY COUNT(*) DESC
        """)
        return [(row[0], row[1]) for row in cur.fetchall()]


def get_category_trends(days: int = 14) -> dict[str, list[tuple[str, int]]]:
    """Тренды по категориям за N дней: {category: [(day, count), ...]}."""
    with _tx() as conn:
        cur = conn.execute("""
            SELECT substr(date, 1, 10) as day, category, COUNT(*)
            FROM leads
            WHERE date IS NOT NULL
            GROUP BY day, category
            ORDER BY day DESC
            LIMIT ?
        """, (days * 4,))  # 4 категории
        rows = cur.fetchall()
    result = {}
    for day, cat, cnt in rows:
        result.setdefault(cat, []).append((day, cnt))
    return result


def get_channel_trends(days: int = 14) -> dict[str, list[tuple[str, int]]]:
    with _tx() as conn:
        cur = conn.execute("""
            SELECT substr(date, 1, 10) as day, channel_title, COUNT(*)
            FROM leads
            WHERE date IS NOT NULL
            GROUP BY day, channel_title
            ORDER BY day DESC
            LIMIT ?
        """, (days * 20,))
        rows = cur.fetchall()
    result = {}
    for day, ch, cnt in rows:
        result.setdefault(ch, []).append((day, cnt))
    return result


def backup_to_json(path: Path) -> int:
    """Экспорт всех лидов в JSON для бэкапа."""
    leads = load_all_leads_full()
    path.write_text(json.dumps(leads, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(leads)


def close_all():
    if hasattr(_thread_local, "conn") and _thread_local.conn:
        _thread_local.conn.close()
        _thread_local.conn = None


if __name__ == "__main__":
    init_db()
    print("DB initialized at", DB_PATH)
    print("Stats:", get_stats())