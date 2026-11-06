"""
Общая логика сканирования каналов.
Используется в bot.py (real-time) и test_monitor.py (batch).
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat

from core.models import Lead, fix_mojibake
from core.patterns import text_matches, text_is_excluded_region, build_patterns, build_geo_patterns
from core.classifier import GeminiClassifier
from core.deduplicator import Deduplicator
from core.notifier import Notifier

log = logging.getLogger("scanner")


@dataclass
class ScanConfig:
    """Конфигурация сканирования."""
    keywords: List[str]
    exclude_regions: List[str]
    scan_limit: int = 1000
    initial_scan_days: int = 60


@dataclass
class ScanResult:
    """Результат сканирования одного канала."""
    leads: List[Lead]
    stats: Dict[str, int]
    max_id_seen: int
    scanned: int


class ChannelScanner:
    """
    Сканирует один канал/чат.
    Не зависит от типа клиента (user/bot) и режима (real-time/batch).
    """

    def __init__(
        self,
        config: ScanConfig,
        classifier: GeminiClassifier,
        deduplicator: Deduplicator,
        notifier: Optional[Notifier] = None,
    ):
        self.config = config
        self.classifier = classifier
        self.deduplicator = deduplicator
        self.notifier = notifier

        # Компилируем паттерны один раз
        self.keyword_patterns = build_patterns(config.keywords)
        self.exclude_patterns = build_geo_patterns(config.exclude_regions)

    async def scan_channel(
        self,
        client: TelegramClient,
        channel: str,
        last_id: int = 0,
        is_first_scan: bool = False,
    ) -> ScanResult:
        """
        Сканирует канал от last_id (или за initial_scan_days для первого раза).
        Возвращает найденные лиды и статистику.
        """
        min_date = None
        if is_first_scan:
            min_date = datetime.now(timezone.utc) - timedelta(days=self.config.initial_scan_days)

        entity = await client.get_entity(channel)
        title = getattr(entity, "title", channel)
        mode = f"первичный скан за {self.config.initial_scan_days} дней" if is_first_scan else f"инкремент (id > {last_id})"
        log.info(f"{'='*60}")
        log.info(f"КАНАЛ: {title}")
        log.info(f"Режим: {mode}")

        candidates = []
        scanned = 0
        max_id_seen = last_id

        async for msg in client.iter_messages(entity, limit=self.config.scan_limit, min_id=last_id):
            if is_first_scan and min_date and msg.date:
                if msg.date < min_date:
                    break
            scanned += 1
            max_id_seen = max(max_id_seen, msg.id)
            text = msg.message or ""
            text = fix_mojibake(text)

            if not text_matches(text, self.keyword_patterns):
                continue

            # Дешёвый префильтр южных регионов — экономим квоту Gemini
            if text_is_excluded_region(text, self.exclude_patterns):
                continue

            candidates.append({
                "id": msg.id,
                "date": msg.date.isoformat() if msg.date else None,
                "text": text,
                "sender_id": msg.sender_id,
                "channel": channel,
                "channel_title": title,
            })

        log.info(f"Просмотрено: {scanned}")
        log.info(f"Прошло keyword-фильтр: {len(candidates)}")

        if not candidates:
            return ScanResult(
                leads=[],
                stats={"hot": 0, "warm": 0, "spam": 0, "noise": 0, "rate_limited": 0, "error": 0},
                max_id_seen=max_id_seen,
                scanned=scanned,
            )

        log.info("\nКлассификация через Gemini...")
        log.info("-" * 60)

        leads = []
        stats = {"hot": 0, "warm": 0, "spam": 0, "noise": 0, "rate_limited": 0, "error": 0}

        for i, m in enumerate(candidates, 1):
            preview = m["text"][:80].replace("\n", " ")
            log.info(f"  [{i}/{len(candidates)}] id={m['id']}: {preview}...")

            # Проверяем дедупликацию ПЕРЕД классификацией
            if self.deduplicator.is_known(m["channel"], m["id"]):
                log.info(f"     → уже известен (channel+id), пропуск")
                continue
            if self.deduplicator.is_text_duplicate(m["text"]):
                log.info(f"     → дубль текста, пропуск без Gemini")
                continue

            result = await self.classifier.classify_async(m["text"])
            cat = result.category
            stats[cat] = stats.get(cat, 0) + 1
            log.info(f"     → {cat}: {result.reason}")

            if result.is_lead:
                lead = Lead(
                    id=m["id"],
                    date=m["date"],
                    text=m["text"],
                    sender_id=m["sender_id"],
                    channel=m["channel"],
                    channel_title=m["channel_title"],
                    category=cat,
                    reason=result.reason,
                )
                leads.append(lead)
                self.deduplicator.add(lead)

                # Отправляем уведомление сразу
                if self.notifier:
                    await self.notifier.send(lead)

        return ScanResult(
            leads=leads,
            stats=stats,
            max_id_seen=max_id_seen,
            scanned=scanned,
        )


class BatchChannelScanner(ChannelScanner):
    """
    Синхронная версия для test_monitor.py (использует classify_sync).
    """

    async def scan_channel(
        self,
        client: TelegramClient,
        channel: str,
        last_id: int = 0,
        is_first_scan: bool = False,
    ) -> ScanResult:
        # Переопределяем только классификацию на sync версию
        min_date = None
        if is_first_scan:
            min_date = datetime.now(timezone.utc) - timedelta(days=self.config.initial_scan_days)

        entity = await client.get_entity(channel)
        title = getattr(entity, "title", channel)
        mode = f"первичный скан за {self.config.initial_scan_days} дней" if is_first_scan else f"инкремент (id > {last_id})"
        log.info(f"{'='*60}")
        log.info(f"КАНАЛ: {title}")
        log.info(f"Режим: {mode}")

        candidates = []
        scanned = 0
        max_id_seen = last_id

        async for msg in client.iter_messages(entity, limit=self.config.scan_limit, min_id=last_id):
            if is_first_scan and min_date and msg.date:
                if msg.date < min_date:
                    break
            scanned += 1
            max_id_seen = max(max_id_seen, msg.id)
            text = msg.message or ""
            text = fix_mojibake(text)

            if not text_matches(text, self.keyword_patterns):
                continue

            if text_is_excluded_region(text, self.exclude_patterns):
                continue

            candidates.append({
                "id": msg.id,
                "date": msg.date.isoformat() if msg.date else None,
                "text": text,
                "sender_id": msg.sender_id,
                "channel": channel,
                "channel_title": title,
            })

        log.info(f"Просмотрено: {scanned}")
        log.info(f"Прошло keyword-фильтр: {len(candidates)}")

        if not candidates:
            return ScanResult(
                leads=[],
                stats={"hot": 0, "warm": 0, "spam": 0, "noise": 0, "rate_limited": 0, "error": 0},
                max_id_seen=max_id_seen,
                scanned=scanned,
            )

        log.info("\nКлассификация через Gemini...")
        log.info("-" * 60)

        leads = []
        stats = {"hot": 0, "warm": 0, "spam": 0, "noise": 0, "rate_limited": 0, "error": 0}

        for i, m in enumerate(candidates, 1):
            preview = m["text"][:80].replace("\n", " ")
            log.info(f"  [{i}/{len(candidates)}] id={m['id']}: {preview}...")

            if self.deduplicator.is_known(m["channel"], m["id"]):
                log.info(f"     → уже известен (channel+id), пропуск")
                continue
            if self.deduplicator.is_text_duplicate(m["text"]):
                log.info(f"     → дубль текста, пропуск без Gemini")
                continue

            # SYNC классификация для batch режима
            result = self.classifier.classify_sync(m["text"])
            cat = result.category
            stats[cat] = stats.get(cat, 0) + 1
            log.info(f"     → {cat}: {result.reason}")

            if result.is_lead:
                lead = Lead(
                    id=m["id"],
                    date=m["date"],
                    text=m["text"],
                    sender_id=m["sender_id"],
                    channel=m["channel"],
                    channel_title=m["channel_title"],
                    category=cat,
                    reason=result.reason,
                )
                leads.append(lead)
                self.deduplicator.add(lead)

                if self.notifier:
                    await self.notifier.send(lead)

                # Пауза между запросами к Gemini (free tier: 15 RPM)
                import time
                time.sleep(5.5)

        return ScanResult(
            leads=leads,
            stats=stats,
            max_id_seen=max_id_seen,
            scanned=scanned,
        )