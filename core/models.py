"""
Общие модели данных для BanditTour Lead Scanner.
Используются в bot.py, test_monitor.py, dashboard_server.py.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Literal
import hashlib
import re


Category = Literal["hot", "warm", "spam", "noise", "rate_limited", "error"]


@dataclass
class ClassificationResult:
    """Результат классификации сообщения Gemini."""
    is_lead: bool
    category: Category
    reason: str

    def __post_init__(self):
        if self.reason and len(self.reason) > 200:
            self.reason = self.reason[:200]


@dataclass
class Lead:
    """Найденный лид."""
    id: int
    date: Optional[str]
    text: str
    sender_id: Optional[int]
    channel: str
    channel_title: str
    category: Category
    reason: str
    classified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    text_hash: Optional[str] = None

    def __post_init__(self):
        if not self.text_hash:
            self.text_hash = normalize_text_hash(self.text)

    @property
    def lead_key(self) -> tuple[str, int]:
        """Ключ для дедупликации: (channel, message_id)."""
        return (self.channel or "?", self.id)

    def to_dict(self) -> dict:
        """Сериализация в dict для JSON/БД."""
        return {
            "id": self.id,
            "date": self.date,
            "text": self.text,
            "sender_id": self.sender_id,
            "channel": self.channel,
            "channel_title": self.channel_title,
            "category": self.category,
            "reason": self.reason,
            "classified_at": self.classified_at,
            "text_hash": self.text_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Lead":
        """Десериализация из dict."""
        return cls(
            id=data.get("id"),
            date=data.get("date"),
            text=data.get("text", ""),
            sender_id=data.get("sender_id"),
            channel=data.get("channel", "?"),
            channel_title=data.get("channel_title", "?"),
            category=data.get("category", "noise"),
            reason=data.get("reason", ""),
            classified_at=data.get("classified_at", datetime.now(timezone.utc).isoformat()),
            text_hash=data.get("text_hash"),
        )


def normalize_text_hash(text: str) -> str:
    """Хэш нормализованного текста для кросс-канального дедупа репостов."""
    if not text:
        return ""
    t = text.lower().replace("ё", "е")
    # Режем ссылки/упоминания — репосты отличаются только ими
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"@\w+", "", t)
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return hashlib.md5(t[:500].encode("utf-8")).hexdigest()[:16]


def fix_mojibake(text: str) -> str:
    """Безопасная эвристика: чиним только цепочки вида 'РџСЂРёРІРµС‚' (3+ подряд пар 'Р/С + не-ASCII')."""
    if not text:
        return text
    _MOJIBAKE_RE = re.compile(r"(?:[РС][^\x00-\x7F]){3,}")
    if not _MOJIBAKE_RE.search(text):
        return text
    try:
        fixed = text.encode("windows-1251").decode("utf-8")
        return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text