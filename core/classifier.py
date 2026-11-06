"""
Gemini-классификатор с поддержкой множественных ключей, ротации и retry.
Общий для bot.py (async) и test_monitor.py (sync).
"""
import asyncio
import json
import logging
import re
import time
from typing import Optional, List

from google import generativeai as genai

from core.models import ClassificationResult, Lead
from core.prompts import CLASSIFY_PROMPT

log = logging.getLogger("classifier")


def init_gemini(api_key: str, model_name: str):
    """Инициализирует модель Gemini."""
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


def _probe_gemini_key(api_key: str, model_name: str) -> tuple[bool, str]:
    """
    Один дешёвый запрос для проверки ключа.
    403 → ключ мёртвый. 429 → ключ валидный, просто сейчас лимит.
    Прочие ошибки (сеть и т.п.) — ключ НЕ помечаем мёртвым, считаем живым.
    """
    try:
        model = init_gemini(api_key, model_name)
        resp = model.generate_content("скажи ок")
        _ = (resp.text or "").strip()
        return True, "OK"
    except Exception as e:
        msg = str(e)
        if any(s in msg for s in ("403", "PERMISSION_DENIED", "API key not valid",
                                  "denied access", "API_KEY_INVALID")):
            return False, "403 доступ запрещён"
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            return True, "жив, но сейчас лимит (429)"
        return True, f"не проверен ({type(e).__name__}: {msg[:60]})"


class GeminiClassifier:
    """
    Классификатор с поддержкой:
    - Множественных API ключей (ротация при 429/403)
    - Retry с экспоненциальным бэкофом
    - Async и sync интерфейсов
    """

    def __init__(
        self,
        api_keys: List[str],
        model_name: str = "gemini-2.5-flash-lite",
        max_retries: int = 3,
    ):
        if not api_keys:
            raise ValueError("Нужен хотя бы один Gemini API ключ")
        self.api_keys = [k for k in api_keys if k]
        if not self.api_keys:
            raise ValueError("Все переданные ключи пустые")
        self.model_name = model_name
        self.max_retries = max_retries
        self._key_idx = 0
        self._dead_keys: set[int] = set()
        self._model = init_gemini(self.api_keys[0], model_name)
        self._validate_keys_on_start()

    def _validate_keys_on_start(self):
        """Проверяет все ключи при старте, помечает мёртвые."""
        log.info(f"Проверка ключей Gemini ({len(self.api_keys)} шт.)...")
        for i, key in enumerate(self.api_keys):
            alive, reason = _probe_gemini_key(key, self.model_name)
            if alive:
                log.info(f"  ключ #{i + 1}: {reason}")
            else:
                self._dead_keys.add(i)
                log.warning(f"  ключ #{i + 1}: МЁРТВЫЙ ({reason}) — будет пропускаться")
        alive_n = len(self.api_keys) - len(self._dead_keys)
        if alive_n > 0:
            for i in range(len(self.api_keys)):
                if i not in self._dead_keys:
                    self._key_idx = i
                    self._model = init_gemini(self.api_keys[i], self.model_name)
                    break
            log.info(f"Итог: ключей {len(self.api_keys)}, живых {alive_n} — "
                     f"стартую с ключа #{self._key_idx + 1}")
        else:
            log.error("НЕТ ЖИВЫХ ключей Gemini — классификация будет падать в error")

    @property
    def current_key_index(self) -> int:
        return self._key_idx

    @property
    def alive_keys_count(self) -> int:
        return len(self.api_keys) - len(self._dead_keys)

    def _rotate_key(self) -> bool:
        """Переключает на следующий РАБОЧИЙ ключ. True — если переключились."""
        n = len(self.api_keys)
        for step in range(1, n + 1):
            i = (self._key_idx + step) % n
            if i in self._dead_keys:
                continue
            if i == self._key_idx:
                break
            self._key_idx = i
            self._model = init_gemini(self.api_keys[i], self.model_name)
            log.warning(f"  ⇨ Переключился на ключ Gemini #{i + 1} из {n}")
            return True
        return False

    def _mark_key_dead(self, reason: str = ""):
        """Помечает текущий ключ нерабочим (403/доступ запрещён)."""
        i = self._key_idx
        if i in self._dead_keys:
            return
        self._dead_keys.add(i)
        alive = len(self.api_keys) - len(self._dead_keys)
        log.warning(f"  ✖ Ключ Gemini #{i + 1} нерабочий ({reason[:80]}); живых: {alive}")
        if alive == 0:
            log.error("  ✖ НЕТ ЖИВЫХ ключей Gemini — классификация невозможна")

    def _clean_json_response(self, raw: str) -> str:
        """Снимает markdown-фенсы ```json ... ```."""
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        return raw.strip()

    def classify_sync(self, text: str) -> ClassificationResult:
        """Синхронная классификация (для test_monitor.py)."""
        if not text or len(text.strip()) < 10:
            return ClassificationResult(False, "noise", "слишком короткое")

        prompt = CLASSIFY_PROMPT.format(message=text[:1500])
        attempt = 0
        rotations = 0
        max_rotations = max(0, len(self.api_keys) - 1)

        while attempt < self.max_retries:
            raw = ""
            try:
                resp = self._model.generate_content(prompt)
                raw = (resp.text or "").strip()
                raw = self._clean_json_response(raw)
                data = json.loads(raw)
                return ClassificationResult(
                    is_lead=bool(data.get("is_lead", False)),
                    category=data.get("category", "noise"),
                    reason=data.get("reason", "")[:200],
                )
            except json.JSONDecodeError as e:
                log.warning(f"Gemini вернул не-JSON (попытка {attempt+1}/{self.max_retries}): {raw[:200]}")
                if attempt == self.max_retries - 1:
                    return ClassificationResult(False, "noise", f"неверный JSON: {e}")
                attempt += 1
                time.sleep(2)
            except Exception as e:
                msg = str(e)
                dead = ("403" in msg or "PERMISSION_DENIED" in msg
                        or "API key not valid" in msg or "denied access" in msg
                        or "API_KEY_INVALID" in msg)
                if dead:
                    self._mark_key_dead(msg)
                    if rotations < max_rotations and self._rotate_key():
                        rotations += 1
                        time.sleep(2)
                        continue
                    return ClassificationResult(False, "error", "нет рабочего ключа Gemini (403)")
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    if rotations < max_rotations and self._rotate_key():
                        rotations += 1
                        time.sleep(3)
                        continue
                    wait = 30
                    m = re.search(r"retry in ([\d.]+)s", msg.lower()) or re.search(r"seconds:\s*(\d+)", msg.lower())
                    if m:
                        try:
                            wait = int(float(m.group(1))) + 2
                        except ValueError:
                            pass
                    if attempt < self.max_retries - 1:
                        log.warning(f"  rate_limited, жду {wait}с (попытка {attempt+1}/{self.max_retries})")
                        time.sleep(wait)
                        attempt += 1
                        continue
                    return ClassificationResult(False, "rate_limited", "лимит Gemini")
                return ClassificationResult(False, "error", f"{type(e).__name__}: {msg[:100]}")
        return ClassificationResult(False, "error", "все попытки исчерпаны")

    async def classify_async(self, text: str) -> ClassificationResult:
        """Асинхронная классификация (для bot.py) — выполняет sync вызов в thread pool."""
        if not text or len(text.strip()) < 10:
            return ClassificationResult(False, "noise", "слишком короткое")

        prompt = CLASSIFY_PROMPT.format(message=text[:1500])
        attempt = 0
        rotations = 0
        max_rotations = max(0, len(self.api_keys) - 1)

        while attempt < self.max_retries:
            raw = ""
            try:
                # generate_content — синхронный сетевой вызов: выполняем в отдельном потоке
                resp = await asyncio.to_thread(self._model.generate_content, prompt)
                raw = (resp.text or "").strip()
                raw = self._clean_json_response(raw)
                data = json.loads(raw)
                return ClassificationResult(
                    is_lead=bool(data.get("is_lead", False)),
                    category=data.get("category", "noise"),
                    reason=data.get("reason", "")[:200],
                )
            except json.JSONDecodeError as e:
                log.warning(f"Gemini вернул не-JSON (попытка {attempt+1}/{self.max_retries}): {raw[:200]}")
                if attempt == self.max_retries - 1:
                    return ClassificationResult(False, "noise", f"неверный JSON: {e}")
                attempt += 1
                await asyncio.sleep(2)
            except Exception as e:
                msg = str(e)
                dead = ("403" in msg or "PERMISSION_DENIED" in msg
                        or "API key not valid" in msg or "denied access" in msg
                        or "API_KEY_INVALID" in msg)
                if dead:
                    self._mark_key_dead(msg)
                    if rotations < max_rotations and self._rotate_key():
                        rotations += 1
                        await asyncio.sleep(2)
                        continue
                    return ClassificationResult(False, "error", "нет рабочего ключа Gemini (403)")
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    if rotations < max_rotations and self._rotate_key():
                        rotations += 1
                        await asyncio.sleep(3)
                        continue
                    wait = 30
                    m = re.search(r"retry in ([\d.]+)s", msg.lower()) or re.search(r"seconds:\s*(\d+)", msg.lower())
                    if m:
                        try:
                            wait = int(float(m.group(1))) + 2
                        except ValueError:
                            pass
                    if attempt < self.max_retries - 1:
                        log.warning(f"  rate_limited, жду {wait}с (попытка {attempt+1}/{self.max_retries})")
                        await asyncio.sleep(wait)
                        attempt += 1
                        continue
                    return ClassificationResult(False, "rate_limited", "лимит Gemini")
                return ClassificationResult(False, "error", f"{type(e).__name__}: {msg[:100]}")
        return ClassificationResult(False, "error", "все попытки исчерпаны")