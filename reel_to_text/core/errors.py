"""Errors the core raises. Interfaces map them to user-facing text."""
from __future__ import annotations


class ReelToTextError(Exception):
    """Base class. `code` is stable and safe to show or return over an API."""
    code = "error"


class InvalidUrl(ReelToTextError):
    code = "invalid_url"


class ReelNotFound(ReelToTextError):
    """Private, deleted or never existed."""
    code = "not_found"


class NotAVideo(ReelToTextError):
    code = "not_a_video"


class ReelTooLong(ReelToTextError):
    code = "too_long"

    def __init__(self, duration: float, limit: int):
        super().__init__(f"duration {duration:.0f}s > limit {limit}s")
        self.duration = duration
        self.limit = limit


class RateLimited(ReelToTextError):
    code = "rate_limited"

    def __init__(self, retry_after: int):
        super().__init__(f"retry after {retry_after}s")
        self.retry_after = retry_after


class GlobalLimitReached(ReelToTextError):
    """The service-wide daily budget is spent."""
    code = "global_limit"


class AccessDenied(ReelToTextError):
    code = "access_denied"


class ProviderUnavailable(ReelToTextError):
    """Instagram provider failed for a reason that is not the reel's fault."""
    code = "provider_unavailable"


class TranscriptionFailed(ReelToTextError):
    code = "transcription_failed"
