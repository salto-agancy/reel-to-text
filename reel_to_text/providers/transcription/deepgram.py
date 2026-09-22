"""Deepgram pre-recorded API: remote URL first, file upload as fallback."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import httpx

from ...core.errors import TranscriptionFailed
from .base import SttResult

LISTEN_URL = "https://api.deepgram.com/v1/listen"


class RemoteFetchFailed(Exception):
    """Deepgram could not download the URL (expired/blocked CDN link). Caller should upload the file."""


def _text_from(data: dict[str, Any]) -> SttResult:
    try:
        channel = data["results"]["channels"][0]
        alt = channel["alternatives"][0]
    except (KeyError, IndexError, TypeError) as e:
        raise TranscriptionFailed("deepgram: unexpected response") from e
    paragraphs = (alt.get("paragraphs") or {}).get("paragraphs") or []
    if paragraphs:
        text = "\n\n".join(
            " ".join(s.get("text", "") for s in p.get("sentences") or []).strip() for p in paragraphs
        ).strip()
    else:
        text = (alt.get("transcript") or "").strip()
    langs = alt.get("languages") or []
    language = channel.get("detected_language") or (langs[0] if langs else "")
    duration = (data.get("metadata") or {}).get("duration")
    return SttResult(text=text, language=language, duration=duration)


class DeepgramStt:
    name = "deepgram"

    def __init__(self, api_key: str, model: str = "nova-3", language: str = "multi",
                 timeout: float = 120.0, base_url: str = LISTEN_URL,
                 transport: Optional[httpx.AsyncBaseTransport] = None):
        self.api_key = api_key
        self.model = model
        self.language = language
        self.timeout = timeout
        self.base_url = base_url
        self._transport = transport

    def params(self) -> dict[str, str]:
        p = {
            "model": self.model,
            # smart_format mangles Russian numerals, punctuation + paragraphs are enough
            "smart_format": "false",
            "punctuate": "true",
            "paragraphs": "true",
        }
        if self.language == "detect":
            p["detect_language"] = "true"
        else:
            p["language"] = self.language
        return p

    async def _post(self, **kwargs: Any) -> httpx.Response:
        timeout = httpx.Timeout(self.timeout, connect=15.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as http:
                return await http.post(
                    self.base_url, params=self.params(),
                    headers={"Authorization": f"Token {self.api_key}", **kwargs.pop("headers", {})},
                    **kwargs,
                )
        except httpx.HTTPError as e:
            raise TranscriptionFailed(f"deepgram network: {type(e).__name__}") from e

    async def transcribe_url(self, url: str) -> SttResult:
        r = await self._post(json={"url": url})
        if r.status_code == 200:
            return _text_from(r.json())
        body = r.text[:300]
        # 400 with a fetch problem = Deepgram could not download the media; other codes are ours
        if r.status_code == 400 and any(
            s in body.lower() for s in ("remote", "url", "fetch", "download", "could not", "failed to")
        ):
            raise RemoteFetchFailed(body)
        raise TranscriptionFailed(f"deepgram http {r.status_code}: {body}")

    async def transcribe_file(self, path: Path, content_type: str) -> SttResult:
        with path.open("rb") as f:
            r = await self._post(content=f.read(), headers={"Content-Type": content_type})
        if r.status_code == 200:
            return _text_from(r.json())
        raise TranscriptionFailed(f"deepgram http {r.status_code}: {r.text[:300]}")
