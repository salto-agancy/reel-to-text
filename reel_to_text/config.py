"""Settings from environment variables (.env is loaded by the entrypoint)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    return float(raw) if raw else default


def _ids(name: str) -> frozenset[int]:
    raw = os.environ.get(name, "")
    return frozenset(int(x) for x in raw.replace(";", ",").split(",") if x.strip())


def _list(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, "").strip() or default
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    # secrets
    telegram_bot_token: str = ""
    deepgram_api_key: str = ""
    hikerapi_key: str = ""

    # instagram providers, tried in order; a provider without its key is skipped
    instagram_providers: list[str] = field(default_factory=lambda: ["hikerapi", "ytdlp"])
    hikerapi_base_url: str = "https://api.hikerapi.com"
    ytdlp_cookies_file: str = ""

    # speech-to-text
    deepgram_model: str = "nova-3"
    deepgram_language: str = "multi"

    # limits
    max_reel_seconds: int = 300
    max_download_mb: int = 100
    rate_limit_per_hour: int = 10
    rate_limit_per_day: int = 30
    http_timeout: float = 30.0
    stt_timeout: float = 120.0

    # access
    access_mode: str = "allowlist"  # allowlist | open
    allowed_user_ids: frozenset[int] = frozenset()
    admin_user_ids: frozenset[int] = frozenset()

    data_dir: Path = Path("data")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
            deepgram_api_key=os.environ.get("DEEPGRAM_API_KEY", "").strip(),
            hikerapi_key=os.environ.get("HIKERAPI_KEY", "").strip(),
            instagram_providers=_list("INSTAGRAM_PROVIDERS", "hikerapi,ytdlp"),
            hikerapi_base_url=os.environ.get("HIKERAPI_BASE_URL", "").strip() or "https://api.hikerapi.com",
            ytdlp_cookies_file=os.environ.get("YTDLP_COOKIES_FILE", "").strip(),
            deepgram_model=os.environ.get("DEEPGRAM_MODEL", "").strip() or "nova-3",
            deepgram_language=os.environ.get("DEEPGRAM_LANGUAGE", "").strip() or "multi",
            max_reel_seconds=_int("MAX_REEL_SECONDS", 300),
            max_download_mb=_int("MAX_DOWNLOAD_MB", 100),
            rate_limit_per_hour=_int("RATE_LIMIT_PER_HOUR", 10),
            rate_limit_per_day=_int("RATE_LIMIT_PER_DAY", 30),
            http_timeout=_float("HTTP_TIMEOUT", 30.0),
            stt_timeout=_float("STT_TIMEOUT", 120.0),
            access_mode=(os.environ.get("ACCESS_MODE", "").strip().lower() or "allowlist"),
            allowed_user_ids=_ids("ALLOWED_USER_IDS"),
            admin_user_ids=_ids("ADMIN_USER_IDS"),
            data_dir=Path(os.environ.get("DATA_DIR", "").strip() or "data"),
        )
