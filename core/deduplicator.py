"""
Дедупликация лидов:
- По (channel, message_id) — основной ключ
- По text_hash — кросс-канальный дедуп репостов
"""
import logging
from typing import Optional, Set, Iterable

from core.models import Lead, normalize_text_hash

log = logging.getLogger("deduplicator")


class Deduplicator:
    """
    Управляет множествами известных лидов для дедупликации.
    Поддерживает персистентное хранение через callback'и.
    """

    def __init__(
        self,
        known_ids: Optional[Set[tuple[str, int]]] = None,
        known_text_hashes: Optional[Set[str]] = None,
    ):
        self.known_ids: Set[tuple[str, int]] = known_ids or set()
        self.known_text_hashes: Set[str] = known_text_hashes or set()

    @classmethod
    def from_leads(cls, leads: Iterable[Lead]) -> "Deduplicator":
        """Создаёт дедупликатор из списка существующих лидов."""
        known_ids = set()
        known_text_hashes = set()
        for lead in leads:
            known_ids.add(lead.lead_key)
            if lead.text_hash:
                known_text_hashes.add(lead.text_hash)
        return cls(known_ids, known_text_hashes)

    def is_known(self, channel: str, msg_id: int) -> bool:
        """Проверяет, известен ли лид по (channel, message_id)."""
        return (channel or "?", msg_id) in self.known_ids

    def is_text_duplicate(self, text: str) -> bool:
        """Проверяет, является ли текст дублем (кросс-канальный дедуп)."""
        h = normalize_text_hash(text)
        return bool(h and h in self.known_text_hashes)

    def add(self, lead: Lead) -> bool:
        """
        Добавляет лид в известные.
        Возвращает True если лид новый, False если дубль.
        """
        key = lead.lead_key
        if key in self.known_ids:
            return False

        self.known_ids.add(key)
        if lead.text_hash:
            self.known_text_hashes.add(lead.text_hash)
        return True

    def get_stats(self) -> dict:
        return {
            "known_ids": len(self.known_ids),
            "known_text_hashes": len(self.known_text_hashes),
        }