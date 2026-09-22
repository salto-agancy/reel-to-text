"""Find an Instagram reel link in free text and pull out the shortcode."""
from __future__ import annotations

import re
from typing import Optional

from .errors import InvalidUrl

# Covers /reel/, /reels/, /p/, /tv/ with optional username prefix, query and fragment.
_URL_RE = re.compile(
    r"https?://(?:www\.|m\.)?(?:instagram\.com|instagr\.am)/"
    r"(?:[A-Za-z0-9_.]+/)?(?:reels?|p|tv)/([A-Za-z0-9_-]{5,})",
    re.IGNORECASE,
)


def find_url(text: str) -> Optional[str]:
    """First Instagram post/reel URL inside arbitrary text (iOS share text, message)."""
    m = _URL_RE.search(text or "")
    return m.group(0) if m else None


def extract_shortcode(text: str) -> str:
    m = _URL_RE.search(text or "")
    if not m:
        raise InvalidUrl("no instagram reel link found")
    return m.group(1)


def canonical_url(shortcode: str) -> str:
    return f"https://www.instagram.com/reel/{shortcode}/"
