"""
Core package for BanditTour Lead Scanner.
Общие модули, используемые в bot.py, test_monitor.py, dashboard_server.py.
"""

from core.models import (
    Lead,
    ClassificationResult,
    Category,
    normalize_text_hash,
    fix_mojibake,
)
from core.patterns import (
    build_patterns,
    build_geo_patterns,
    text_matches,
    text_is_excluded_region,
    NORTH_GEO_KEYWORDS,
    NORTH_GEO_PATTERNS,
)
from core.prompts import CLASSIFY_PROMPT
from core.classifier import GeminiClassifier
from core.notifier import Notifier, TelegramBotNotifier, SavedMessagesNotifier
from core.deduplicator import Deduplicator
from core.scanner import ChannelScanner, BatchChannelScanner, ScanConfig, ScanResult
from core.config import Config, config

__all__ = [
    # models
    "Lead",
    "ClassificationResult",
    "Category",
    "normalize_text_hash",
    "fix_mojibake",
    # patterns
    "build_patterns",
    "build_geo_patterns",
    "text_matches",
    "text_is_excluded_region",
    "NORTH_GEO_KEYWORDS",
    "NORTH_GEO_PATTERNS",
    # prompts
    "CLASSIFY_PROMPT",
    # classifier
    "GeminiClassifier",
    # notifier
    "Notifier",
    "TelegramBotNotifier",
    "SavedMessagesNotifier",
    # deduplicator
    "Deduplicator",
    # scanner
    "ChannelScanner",
    "BatchChannelScanner",
    "ScanConfig",
    "ScanResult",
    # config
    "Config",
    "config",
]