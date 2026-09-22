"""The core: Instagram URL -> InstagramProvider -> SpeechToText -> Transcript.

Every interface (Telegram now, MCP and iOS Shortcut later) calls ReelToText.transcribe()
and only formats the result. No interface talks to providers directly.
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

import httpx

from ..providers.instagram.base import InstagramProvider
from ..providers.transcription.base import SpeechToText
from ..providers.transcription.deepgram import RemoteFetchFailed
from .errors import (NotAVideo, ProviderUnavailable, ReelNotFound, ReelTooLong,
                     TranscriptionFailed)
from .limits import RateLimiter
from .models import ReelMedia, Transcript
from .store import Store
from .urls import canonical_url, extract_shortcode

log = logging.getLogger("reel_to_text.core")


class ReelToText:
    def __init__(self, instagram: Sequence[InstagramProvider], stt: SpeechToText, store: Store,
                 limiter: RateLimiter, max_reel_seconds: int = 300, max_download_mb: int = 100,
                 http_timeout: float = 30.0, tmp_dir: Optional[Path] = None,
                 download_transport: Optional[httpx.AsyncBaseTransport] = None):
        if not instagram:
            raise ValueError("at least one Instagram provider is required")
        self.instagram = list(instagram)
        self.stt = stt
        self.store = store
        self.limiter = limiter
        self.max_reel_seconds = max_reel_seconds
        self.max_download_bytes = max_download_mb * 1024 * 1024
        self.http_timeout = http_timeout
        self.tmp_dir = tmp_dir
        self._download_transport = download_transport
        self._inflight: dict[str, asyncio.Future] = {}

    async def transcribe(self, text_or_url: str, requester: str = "anonymous",
                         unlimited: bool = False) -> Transcript:
        """Main entry point. `requester` is a stable id for rate limiting ("tg:123")."""
        shortcode = extract_shortcode(text_or_url)

        cached = self.store.get_transcript(shortcode)
        if cached:
            cached.cached = True
            log.info("cache_hit shortcode=%s requester=%s", shortcode, requester)
            return cached

        # the same reel already in progress (double tap, two users): wait for it, pay once
        running = self._inflight.get(shortcode)
        if running:
            log.info("join_inflight shortcode=%s requester=%s", shortcode, requester)
            result = await asyncio.shield(running)
            return Transcript.from_dict({**result.to_dict(), "cached": True})

        if not unlimited:
            self.limiter.check(requester)

        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._inflight[shortcode] = fut
        try:
            if not unlimited:
                self.limiter.record(requester)
            transcript = await self._run(shortcode)
            self.store.put_transcript(transcript)
            fut.set_result(transcript)
            return transcript
        except asyncio.CancelledError:
            fut.cancel()
            raise
        except Exception as e:
            fut.set_exception(e)
            fut.exception()  # mark retrieved, joiners re-raise it themselves
            raise
        finally:
            self._inflight.pop(shortcode, None)

    async def _run(self, shortcode: str) -> Transcript:
        media = await self._get_media(shortcode)
        if media.duration and media.duration > self.max_reel_seconds:
            raise ReelTooLong(media.duration, self.max_reel_seconds)

        try:
            result = await self.stt.transcribe_url(media.video_url)
            path = "remote_url"
        except RemoteFetchFailed as e:
            log.warning("remote_fetch_failed shortcode=%s detail=%s -> upload fallback", shortcode, str(e)[:120])
            result = await self._transcribe_by_upload(media)
            path = "upload"

        duration = media.duration or result.duration
        log.info("transcribed shortcode=%s provider=%s path=%s duration=%s chars=%d lang=%s",
                 shortcode, media.provider, path, duration, len(result.text), result.language)
        return Transcript(
            text=result.text,
            source_url=canonical_url(shortcode),
            shortcode=shortcode,
            author=media.author,
            caption=media.caption,
            duration=duration,
            language=result.language,
            instagram_provider=media.provider,
            stt_provider=self.stt.name,
            stt_path=path,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    async def _get_media(self, shortcode: str) -> ReelMedia:
        last: Optional[Exception] = None
        for provider in self.instagram:
            try:
                media = await provider.get_reel(shortcode)
                log.info("media shortcode=%s provider=%s duration=%s", shortcode, provider.name, media.duration)
                return media
            except (ReelNotFound, NotAVideo):
                raise  # the reel itself is the problem, another provider will not help
            except ProviderUnavailable as e:
                log.warning("provider_failed provider=%s shortcode=%s err=%s", provider.name, shortcode, e)
                last = e
        raise ProviderUnavailable(str(last) if last else "no instagram provider available")

    async def _transcribe_by_upload(self, media: ReelMedia):
        with tempfile.TemporaryDirectory(dir=self.tmp_dir, prefix="reel-") as tmp:
            path = Path(tmp) / f"{media.shortcode}.mp4"
            await self._download(media.video_url, path)
            return await self.stt.transcribe_file(path, "video/mp4")
        # the temporary directory and the video are removed here

    async def _download(self, url: str, path: Path) -> None:
        size = 0
        headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"}
        try:
            async with httpx.AsyncClient(timeout=self.http_timeout, follow_redirects=True,
                                         transport=self._download_transport) as http:
                async with http.stream("GET", url, headers=headers) as r:
                    if r.status_code != 200:
                        raise TranscriptionFailed(f"video download http {r.status_code}")
                    with path.open("wb") as f:
                        async for chunk in r.aiter_bytes():
                            size += len(chunk)
                            if size > self.max_download_bytes:
                                raise TranscriptionFailed("video is larger than MAX_DOWNLOAD_MB")
                            f.write(chunk)
        except httpx.HTTPError as e:
            raise TranscriptionFailed(f"video download: {type(e).__name__}") from e
