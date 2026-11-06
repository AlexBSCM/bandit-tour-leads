"""
Автоматические бэкапы для BanditTour.
- SQLite БД (leads.db)
- scan_state.json
- test_config.json (без секретов в бэкапе — только структура)
Хранит последние N бэкапов с ротацией.
"""
import json
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from common import BASE_DIR, STATE_PATH, CONFIG_PATH

DB_PATH = BASE_DIR / "leads.db"
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

# Храним последние 30 бэкапов (по одному в день за месяц)
MAX_BACKUPS = 30
BACKUP_INTERVAL_HOURS = 6  # как часто проверять/делать бэкап

_backup_thread = None
_stop_backup = threading.Event()


def _make_backup_name(prefix: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return BACKUP_DIR / f"{prefix}_{ts}.backup"


def backup_database() -> Path | None:
    """Создаёт консистентный бэкап SQLite через .backup API (online backup)."""
    if not DB_PATH.exists():
        return None
    dest = _make_backup_name("leads_db")
    try:
        # online backup — не блокирует запись в основную БД
        src_conn = sqlite3.connect(DB_PATH)
        dst_conn = sqlite3.connect(dest)
        with dst_conn:
            src_conn.backup(dst_conn)
        src_conn.close()
        dst_conn.close()
        return dest
    except Exception as e:
        print(f"Backup DB failed: {e}")
        try:
            dest.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def backup_state() -> Path | None:
    """Бэкап scan_state.json."""
    if not STATE_PATH.exists():
        return None
    dest = _make_backup_name("scan_state")
    try:
        shutil.copy2(STATE_PATH, dest)
        return dest
    except Exception as e:
        print(f"Backup state failed: {e}")
        return None


def backup_config() -> Path | None:
    """Бэкап конфига (только структура, секреты не сохраняем в отдельный файл — они и так в test_config.json)."""
    if not CONFIG_PATH.exists():
        return None
    dest = _make_backup_name("config")
    try:
        # копируем как есть — test_config.json уже в .gitignore
        shutil.copy2(CONFIG_PATH, dest)
        return dest
    except Exception as e:
        print(f"Backup config failed: {e}")
        return None


def rotate_backups():
    """Удаляет старые бэкапы, оставляя MAX_BACKUPS последних."""
    try:
        all_backups = sorted(BACKUP_DIR.glob("*.backup"), key=lambda p: p.stat().st_mtime)
        for old in all_backups[:-MAX_BACKUPS]:
            try:
                old.unlink()
            except Exception:
                pass
    except Exception:
        pass


def run_backup_cycle():
    """Один цикл бэкапа: БД + state + config + ротация."""
    results = {}
    results["db"] = backup_database()
    results["state"] = backup_state()
    results["config"] = backup_config()
    rotate_backups()
    return results


def start_background_backup(interval_hours: float = BACKUP_INTERVAL_HOURS):
    """Запускает фоновый поток периодических бэкапов."""
    global _backup_thread
    if _backup_thread and _backup_thread.is_alive():
        return

    def worker():
        while not _stop_backup.wait(interval_hours * 3600):
            try:
                run_backup_cycle()
            except Exception as e:
                print(f"Background backup error: {e}")

    _backup_thread = threading.Thread(target=worker, daemon=True, name="backup-worker")
    _stop_backup.clear()
    _backup_thread.start()
    print(f"Автобэкап запущен: каждые {interval_hours}ч, хранение {MAX_BACKUPS} копий")


def stop_background_backup():
    _stop_backup.set()
    if _backup_thread:
        _backup_thread.join(timeout=5)


def list_backups() -> list[dict]:
    """Список доступных бэкапов для восстановления."""
    out = []
    for p in sorted(BACKUP_DIR.glob("*.backup"), key=lambda x: x.stat().st_mtime, reverse=True):
        st = p.stat()
        out.append({
            "file": p.name,
            "size": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        })
    return out


def restore_database(backup_file: str) -> bool:
    """Восстанавливает БД из бэкапа (требует остановки бота)."""
    src = BACKUP_DIR / backup_file
    if not src.exists():
        return False
    try:
        # закрываем текущие соединения
        from leads_db import close_all
        close_all()
        # заменяем файл атомарно
        tmp = DB_PATH.with_suffix(".db.tmp")
        shutil.copy2(src, tmp)
        tmp.replace(DB_PATH)
        return True
    except Exception as e:
        print(f"Restore failed: {e}")
        return False


if __name__ == "__main__":
    # ручной запуск: python backup.py
    res = run_backup_cycle()
    print("Backup done:", {k: str(v) for k, v in res.items()})
    print("Available:", list_backups())