"""
Построение regex-паттернов для ключевых слов и гео-фильтров.
Общая логика для bot.py и test_monitor.py.
"""
import re
from typing import List, Pattern


def build_patterns(keywords: List[str]) -> List[Pattern]:
    """
    Компилирует keywords в regex с границами слов для коротких английских.
    
    Для английских слов <= 15 символов использует \b (word boundary).
    Для остальных — простое escape-совпадение.
    """
    patterns = []
    for kw in keywords:
        if re.fullmatch(r"[a-zA-Z\s]+", kw) and len(kw) <= 15:
            pat = r"\b" + re.escape(kw) + r"\b"
        else:
            pat = re.escape(kw)
        patterns.append(re.compile(pat, re.IGNORECASE))
    return patterns


def build_geo_patterns(keywords: List[str]) -> List[Pattern]:
    """
    Паттерны для гео с учётом русских склонений:
    Паттайя/Паттайе/Паттайю, Пай/пая/паю/пае/паем и т.д.
    """
    patterns = []
    for kw in keywords:
        k = kw.strip().lower()
        if not k:
            continue
        # Особые короткие: Пай -> пай/пая/паю/пае/паем
        if k in ("пай",):
            patterns.append(re.compile(r"\bпа[йяюе]\w*\b", re.IGNORECASE))
            continue
        if k in ("pai",):
            patterns.append(re.compile(r"\bpai\b", re.IGNORECASE))
            continue
        if re.fullmatch(r"[a-z\s]+", k):
            # Английский не склоняется — точное совпадение
            patterns.append(re.compile(r"\b" + re.escape(k) + r"\b", re.IGNORECASE))
            continue
        # Русский: берём основу (первые 5 букв или len-2) + любые окончания
        if " " in k:
            # Фразы: каждое слово со склонением
            parts = []
            for w in k.split():
                if len(w) <= 4:
                    parts.append(re.escape(w))
                else:
                    stem = w[: max(4, len(w) - 2)]
                    parts.append(re.escape(stem) + r"\w*")
            patterns.append(re.compile(r"\b" + r"\s+".join(parts), re.IGNORECASE))
        else:
            if len(k) <= 4:
                patterns.append(re.compile(r"\b" + re.escape(k) + r"\b", re.IGNORECASE))
            else:
                stem = k[: max(4, len(k) - 2)]
                patterns.append(re.compile(r"\b" + re.escape(stem) + r"\w*", re.IGNORECASE))
    return patterns


def text_matches(text: str, patterns: List[Pattern]) -> bool:
    """Проверяет, соответствует ли текст хотя бы одному паттерну."""
    if not text:
        return False
    return any(p.search(text) for p in patterns)


# Гео-маркеры севера: только при их наличии сообщение может быть лидом.
# Используются для дешёвого префильтра: если в тексте есть exclude-регион
# (Паттайя/Пхукет/...) и НЕТ северного маркера — в Gemini не идём вообще.
NORTH_GEO_KEYWORDS = [
    "чиангмай", "чианг май", "chiang mai",
    "чианграй", "чианг рай", "chiang rai",
    "золотой треугольник", "golden triangle",
    "мэхонгсон", "mae hong son",
    "север тайланд", "северный таиланд",
    "север тайланда", "север таиланда",
    "northern thailand", "north thailand",
    "пай", "pai",
]
NORTH_GEO_PATTERNS = build_geo_patterns(NORTH_GEO_KEYWORDS)


def text_is_excluded_region(text: str, exclude_patterns: List[Pattern]) -> bool:
    """
    True — сообщение точно не про север: есть южный маркер, северного нет.
    Смешанный случай "был в Паттайе, еду в Чиангмай" — отдаём Gemini.
    """
    if not text or not exclude_patterns:
        return False
    if not any(p.search(text) for p in exclude_patterns):
        return False
    # Смешанный случай — отдаём Gemini
    if any(p.search(text) for p in NORTH_GEO_PATTERNS):
        return False
    return True