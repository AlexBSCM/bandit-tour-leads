"""
Общие утилиты для BanditTour — без зависимостей от bot.py / leads_db.py
чтобы избежать циклических импортов.
Каноническая реализация — в core.models, здесь тонкие реэкспорты
для обратной совместимости.
"""
import json
from pathlib import Path

from core.models import normalize_text_hash, fix_mojibake  # noqa: F401 — реэкспорт

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "test_config.json"
CHANNELS_PATH = BASE_DIR / "channels.json"
STATE_PATH = BASE_DIR / "scan_state.json"
SESSION_USER = str(BASE_DIR / "session_user")
SESSION_BOT = str(BASE_DIR / "session_bot")
LOG_DIR = BASE_DIR / "logs"


def _atomic_write_json(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)  # атомарно, нет полузаписанного файла при краше


def _lead_key(lead_or_channel, msg_id=None):
    """Ключ дедупликации: (канал, id). ID сообщений уникальны только внутри канала."""
    if isinstance(lead_or_channel, dict):
        return (lead_or_channel.get("channel") or "?", lead_or_channel.get("id"))
    return (lead_or_channel or "?", msg_id)