"""Build the core from Settings. Interfaces call build_core() and nothing else."""
from __future__ import annotations

import logging

from ..config import Settings
from ..providers.instagram.hikerapi import HikerApiProvider
from ..providers.instagram.ytdlp import YtDlpProvider
from ..providers.transcription.deepgram import DeepgramStt
from .limits import RateLimiter
from .service import ReelToText
from .store import Store

log = logging.getLogger("reel_to_text")


def build_instagram_providers(s: Settings) -> list:
    providers = []
    for name in s.instagram_providers:
        if name == "hikerapi":
            if s.hikerapi_key:
                providers.append(HikerApiProvider(s.hikerapi_key, s.hikerapi_base_url, s.http_timeout))
            else:
                log.warning("HIKERAPI_KEY is empty: hikerapi provider skipped")
        elif name == "ytdlp":
            providers.append(YtDlpProvider(s.ytdlp_cookies_file, s.http_timeout))
        else:
            log.warning("unknown instagram provider %r ignored", name)
    return providers


def build_core(s: Settings) -> ReelToText:
    if not s.deepgram_api_key:
        raise SystemExit("DEEPGRAM_API_KEY is not set")
    providers = build_instagram_providers(s)
    if not providers:
        raise SystemExit("no Instagram provider configured (set HIKERAPI_KEY or add ytdlp)")
    store = Store(s.data_dir / "reel_to_text.sqlite")
    tmp = s.data_dir / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    return ReelToText(
        instagram=providers,
        stt=DeepgramStt(s.deepgram_api_key, s.deepgram_model, s.deepgram_language, s.stt_timeout),
        store=store,
        limiter=RateLimiter(store, s.rate_limit_per_hour, s.rate_limit_per_day, s.global_daily_limit),
        max_reel_seconds=s.max_reel_seconds,
        max_download_mb=s.max_download_mb,
        http_timeout=s.http_timeout,
        tmp_dir=tmp,
    )
