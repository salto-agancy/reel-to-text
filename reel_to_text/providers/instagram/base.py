"""Instagram provider contract. Swap the source of reels without touching the core."""
from __future__ import annotations

from typing import Protocol

from ...core.models import ReelMedia


class InstagramProvider(Protocol):
    name: str

    async def get_reel(self, shortcode: str) -> ReelMedia:
        """Return media with a direct video URL.

        Raises ReelNotFound (private/deleted: final, do not try other providers),
        NotAVideo (final), ProviderUnavailable (try the next provider).
        """
        ...
