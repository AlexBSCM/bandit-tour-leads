"""
Отправка уведомлений о лидах.
Общий код для bot.py (Telegram bot API) и test_monitor.py (Saved Messages).
"""
import logging
from typing import Optional

from core.models import Lead

log = logging.getLogger("notifier")

CATEGORY_EMOJI = {"hot": "🔥", "warm": "🌤", "spam": "🗑", "noise": "❌"}

NOTIFY_TEMPLATE = """🎯 НОВЫЙ ЛИД — BanditTour

📍 Канал: {channel}
📅 Дата: {date}
🏷 Категория: {category_emoji} {category}
👤 Sender ID: {sender_id}
🔢 Message ID: {msg_id}
🤖 Причина: {reason}

💬 Текст сообщения:
---
{text}
---
🔗 Ссылка: {link}"""


class Notifier:
    """Базовый класс для уведомлений."""

    def __init__(self):
        self.sent_count = 0
        self.failed_count = 0

    def format_notification(self, lead: Lead) -> str:
        """Форматирует уведомление для лида."""
        return NOTIFY_TEMPLATE.format(
            channel=lead.channel_title or lead.channel,
            date=lead.date or "?",
            category_emoji=CATEGORY_EMOJI.get(lead.category, "❓"),
            category=lead.category.upper(),
            sender_id=lead.sender_id or "?",
            msg_id=lead.id,
            reason=lead.reason,
            text=lead.text[:1500],
            link=f"https://t.me/{lead.channel.lstrip('@')}/{lead.id}",
        )


class TelegramBotNotifier(Notifier):
    """Уведомления через Bot API (bot.py)."""

    def __init__(self, bot_client, notify_chat_id: int):
        super().__init__()
        self.bot_client = bot_client
        self.notify_chat_id = notify_chat_id

    async def send(self, lead: Lead) -> bool:
        """Отправляет уведомление в указанный чат."""
        try:
            text = self.format_notification(lead)
            await self.bot_client.send_message(self.notify_chat_id, text, link_preview=False)
            self.sent_count += 1
            return True
        except Exception as e:
            self.failed_count += 1
            log.error(f"Ошибка отправки уведомления: {type(e).__name__}: {e}")
            return False


class SavedMessagesNotifier(Notifier):
    """Уведомления в Saved Messages (test_monitor.py)."""

    def __init__(self, user_client):
        super().__init__()
        self.user_client = user_client

    async def send(self, lead: Lead) -> bool:
        """Отправляет уведомление в Saved Messages (me)."""
        try:
            text = self.format_notification(lead)
            await self.user_client.send_message("me", text, link_preview=False)
            self.sent_count += 1
            return True
        except Exception as e:
            self.failed_count += 1
            log.error(f"Ошибка отправки уведомления: {type(e).__name__}: {e}")
            return False