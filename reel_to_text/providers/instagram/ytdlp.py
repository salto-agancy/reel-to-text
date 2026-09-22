"""yt-dlp fallback: no paid API, but breaks whenever Instagram changes things.

Keep it as the last provider in INSTAGRAM_PROVIDERS, never the only one.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from ...core.errors import NotAVideo, ProviderUnavailable, ReelNotFound
from ...core.models import ReelMedia
from ...core.urls import canonical_url

# "empty media response" is what Instagram gives yt-dlp for private, deleted and made-up codes
_NOT_FOUND_HINTS = ("not available", "does not exist", "private", "404", "removed", "empty media response")


def _best_url(info: dict[str, Any]) -> Optional[str]:
    # a single progressive mp4 with audio is what Deepgram needs
    formats = [f for f in info.get("formats") or [] if f.get("url")]
    with_audio = [f for f in formats if f.get("acodec") not in (None, "none")]
    progressive = [f for f in with_audio if f.get("vcodec") not in (None, "none")]
    for group in (progressive, with_audio):
        if group:
            return max(group, key=lambda f: (f.get("height") or 0, f.get("tbr") or 0))["url"]
    return info.get("url")


class YtDlpProvider:
    name = "ytdlp"

    def __init__(self, cookies_file: str = "", timeout: float = 30.0):
        self.cookies_file = cookies_file
        self.timeout = timeout

    def _extract(self, url: str) -> dict[str, Any]:
        import yt_dlp  # optional dependency

        opts: dict[str, Any] = {
            "quiet": True, "no_warnings": True, "skip_download": True,
            "socket_timeout": self.timeout,
        }
        if self.cookies_file:
            opts["cookiefile"] = self.cookies_file
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    async def get_reel(self, shortcode: str) -> ReelMedia:
        try:
            info = await asyncio.wait_for(
                asyncio.to_thread(self._extract, canonical_url(shortcode)), self.timeout * 2
            )
        except ImportError as e:
            raise ProviderUnavailable("yt-dlp is not installed") from e
        except asyncio.TimeoutError as e:
            raise ProviderUnavailable("yt-dlp timeout") from e
        except Exception as e:  # yt-dlp raises DownloadError for everything
            msg = str(e).lower()
            if any(h in msg for h in _NOT_FOUND_HINTS) and "429" not in msg:
                raise ReelNotFound(shortcode) from e
            raise ProviderUnavailable(f"yt-dlp: {str(e)[:200]}") from e

        if info.get("_type") == "playlist":  # carousel
            entries = [e for e in info.get("entries") or [] if e]
            info = entries[0] if entries else {}
        url = _best_url(info)
        if not url:
            raise NotAVideo(shortcode)
        return ReelMedia(
            shortcode=shortcode,
            video_url=url,
            duration=float(info["duration"]) if info.get("duration") else None,
            author=info.get("channel") or info.get("uploader_id") or info.get("uploader") or "",
            caption=info.get("description") or "",
            provider=self.name,
        )
