"""HikerAPI: GET /v1/media/by/code -> media object with a direct video_url."""
from __future__ import annotations

from typing import Any, Optional

import httpx

from ...core.errors import NotAVideo, ProviderUnavailable, ReelNotFound
from ...core.models import ReelMedia

VIDEO = 2


def _pick_video(data: dict[str, Any]) -> tuple[Optional[str], Optional[float]]:
    if data.get("video_url"):
        return data["video_url"], data.get("video_duration") or None
    # carousel: first video slide
    for res in data.get("resources") or []:
        if res.get("media_type") == VIDEO and res.get("video_url"):
            return res["video_url"], res.get("video_duration") or data.get("video_duration") or None
    versions = data.get("video_versions") or []
    if versions and versions[0].get("url"):
        return versions[0]["url"], data.get("video_duration") or None
    return None, None


class HikerApiProvider:
    name = "hikerapi"

    def __init__(self, api_key: str, base_url: str = "https://api.hikerapi.com",
                 timeout: float = 30.0, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport  # tests inject httpx.MockTransport

    async def get_reel(self, shortcode: str) -> ReelMedia:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as http:
                r = await http.get(
                    f"{self.base_url}/v1/media/by/code",
                    params={"code": shortcode},
                    headers={"x-access-key": self.api_key, "accept": "application/json"},
                )
        except httpx.HTTPError as e:
            raise ProviderUnavailable(f"hikerapi network: {type(e).__name__}") from e

        if r.status_code == 404:
            raise ReelNotFound(shortcode)
        if r.status_code != 200:
            # 401/403 bad key, 402 no balance, 429, 5xx: not the reel's fault
            raise ProviderUnavailable(f"hikerapi http {r.status_code}: {r.text[:200]}")
        try:
            data = r.json()
        except ValueError as e:
            raise ProviderUnavailable("hikerapi invalid json") from e
        if not isinstance(data, dict):
            raise ProviderUnavailable("hikerapi unexpected body")

        video_url, duration = _pick_video(data)
        if not video_url:
            raise NotAVideo(shortcode)
        user = data.get("user") or {}
        return ReelMedia(
            shortcode=shortcode,
            video_url=video_url,
            duration=float(duration) if duration else None,
            author=user.get("username") or "",
            caption=data.get("caption_text") or "",
            provider=self.name,
        )
