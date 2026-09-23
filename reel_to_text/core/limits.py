"""Per-requester rate limit over a sliding hour and day window."""
from __future__ import annotations

import time
from typing import Callable

from .errors import GlobalLimitReached, RateLimited
from .store import Store


class RateLimiter:
    def __init__(self, store: Store, per_hour: int, per_day: int, global_per_day: int = 0,
                 clock: Callable[[], float] = time.time):
        self.store = store
        self.windows = [(3600, per_hour), (86400, per_day)]
        self.global_per_day = global_per_day  # cap on paid requests from everyone, protects the balance
        self.clock = clock

    def check(self, requester: str) -> None:
        now = self.clock()
        for window, limit in self.windows:
            if limit <= 0:
                continue
            since = now - window
            if self.store.count_requests(requester, since) >= limit:
                oldest = self.store.oldest_request(requester, since) or now
                raise RateLimited(max(1, int(oldest + window - now)))
        if self.global_per_day > 0 and self.store.count_all_requests(now - 86400) >= self.global_per_day:
            raise GlobalLimitReached()

    def record(self, requester: str) -> None:
        self.store.add_request(requester, self.clock())
