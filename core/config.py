"""
Централизованная конфигурация без внешних зависимостей.
Приоритет: ENV vars (BANDIT_*) > test_config.json > значения по умолчанию.
"""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


def _base_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_json_config(base_dir: Path) -> dict:
    config_path = base_dir / "test_config.json"
    if not config_path.exists():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    # Каналы живут в channels.json, секретов там нет
    try:
        channels_path = base_dir / "channels.json"
        if channels_path.exists():
            ch_data = json.loads(channels_path.read_text(encoding="utf-8-sig"))
            if isinstance(ch_data, dict):
                ch_data = ch_data.get("channels", [])
            if isinstance(ch_data, list) and ch_data:
                data["channels"] = [str(c) for c in ch_data]
    except Exception:
        pass
    # Нормализуем gemini_api_keys: поддержка старого формата gemini_api_key
    if "gemini_api_keys" not in data and data.get("gemini_api_key"):
        data["gemini_api_keys"] = [data["gemini_api_key"]]
    return data


def _apply_env_overrides(data: dict) -> dict:
    env_map = {
        "api_id": os.environ.get("BANDIT_API_ID"),
        "api_hash": os.environ.get("BANDIT_API_HASH"),
        "bot_token": os.environ.get("BANDIT_BOT_TOKEN"),
        "notify_chat_id": os.environ.get("BANDIT_NOTIFY_CHAT_ID"),
        "gemini_api_key": os.environ.get("BANDIT_GEMINI_API_KEY"),
        "gemini_model": os.environ.get("BANDIT_GEMINI_MODEL"),
        "dashboard_token": os.environ.get("BANDIT_DASH_TOKEN"),
    }
    for key, val in env_map.items():
        if val:
            data[key] = val
    keys_env = os.environ.get("BANDIT_GEMINI_API_KEYS")
    if keys_env:
        data["gemini_api_keys"] = [k.strip() for k in keys_env.split(",") if k.strip()]
    return data


@dataclass
class Config:
    api_id: int = 0
    api_hash: str = ""
    bot_token: str = ""
    notify_chat_id: int = 0
    gemini_api_keys: List[str] = field(default_factory=list)
    gemini_model: str = "gemini-2.5-flash-lite"
    dashboard_token: str = ""
    channels: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    exclude_regions: List[str] = field(default_factory=list)
    scan_limit: int = 1000
    initial_scan_days: int = 60
    base_dir: Path = field(default_factory=_base_dir)
    session_user: str = ""
    session_bot: str = ""

    def __init__(self, _data: dict | None = None, **kwargs):
        base = Path(kwargs.get("base_dir") or _base_dir())
        object.__setattr__(self, "base_dir", base)
        data = dict(_load_json_config(base))
        data = _apply_env_overrides(data)
        if _data:
            data.update(_data)
        data.update(kwargs)
        # прямое присваивание без рекурсии
        object.__setattr__(self, "api_id", self._to_int(data.get("api_id", 0)))
        object.__setattr__(self, "api_hash", str(data.get("api_hash") or ""))
        object.__setattr__(self, "bot_token", str(data.get("bot_token") or ""))
        object.__setattr__(self, "notify_chat_id", self._to_int(data.get("notify_chat_id", 0)))
        keys = data.get("gemini_api_keys")
        if not keys and data.get("gemini_api_key"):
            keys = [data.get("gemini_api_key")]
        if isinstance(keys, str):
            keys = [keys]
        object.__setattr__(self, "gemini_api_keys", [k for k in (keys or []) if k])
        object.__setattr__(self, "gemini_model", str(data.get("gemini_model") or "gemini-2.5-flash-lite"))
        object.__setattr__(self, "dashboard_token", str(data.get("dashboard_token") or ""))
        object.__setattr__(self, "channels", [str(c) for c in (data.get("channels") or [])])
        object.__setattr__(self, "keywords", [str(c) for c in (data.get("keywords") or [])])
        object.__setattr__(self, "exclude_regions", [str(c) for c in (data.get("exclude_regions") or [])])
        object.__setattr__(self, "scan_limit", self._to_int(data.get("scan_limit", 1000), 1000))
        object.__setattr__(self, "initial_scan_days", self._to_int(data.get("initial_scan_days", 60), 60))
        object.__setattr__(self, "session_user", str(data.get("session_user") or str(base / "session_user")))
        object.__setattr__(self, "session_bot", str(data.get("session_bot") or str(base / "session_bot")))

    @staticmethod
    def _to_int(val, default: int = 0) -> int:
        try:
            if isinstance(val, str) and not val.strip().lstrip("-").isdigit():
                return default
            return int(val)
        except Exception:
            return default

    @property
    def gemini_api_key(self) -> str:
        return self.gemini_api_keys[0] if self.gemini_api_keys else ""

    @property
    def is_configured(self) -> bool:
        return bool(self.api_id and self.api_hash and self.bot_token and self.notify_chat_id and self.gemini_api_keys)

    def save_to_json(self, path=None) -> None:
        from common import _atomic_write_json
        target = Path(path) if path else (self.base_dir / "test_config.json")
        safe_data = {
            "channels": self.channels,
            "keywords": self.keywords,
            "exclude_regions": self.exclude_regions,
            "scan_limit": self.scan_limit,
            "initial_scan_days": self.initial_scan_days,
            "gemini_model": self.gemini_model,
            "dashboard_token": self.dashboard_token,
        }
        _atomic_write_json(target, safe_data)


def get_config(**kwargs) -> Config:
    return Config(**kwargs)


try:
    config = Config()
except Exception:
    config = None  # type: ignore
