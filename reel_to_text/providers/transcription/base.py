"""Speech-to-text contract."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class SttResult:
    text: str
    language: str = ""
    duration: float | None = None


class SpeechToText(Protocol):
    name: str

    async def transcribe_url(self, url: str) -> SttResult:
        """Let the STT service fetch the media itself. Raises RemoteFetchFailed if it could not."""
        ...

    async def transcribe_file(self, path: Path, content_type: str) -> SttResult:
        ...
