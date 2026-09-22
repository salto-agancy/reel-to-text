"""Data objects shared by every interface (Telegram, MCP, HTTP)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class ReelMedia:
    """What an Instagram provider returns: where the video is and what it is."""
    shortcode: str
    video_url: str
    duration: Optional[float] = None
    author: str = ""
    caption: str = ""
    provider: str = ""


@dataclass
class Transcript:
    """The one standard result object: text + where it came from."""
    text: str
    source_url: str
    shortcode: str
    author: str = ""
    caption: str = ""
    duration: Optional[float] = None
    language: str = ""
    instagram_provider: str = ""
    stt_provider: str = ""
    stt_path: str = ""  # "remote_url" or "upload"
    created_at: str = ""
    cached: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Transcript":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)
