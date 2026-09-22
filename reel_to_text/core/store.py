"""SQLite storage: transcript cache by shortcode and per-user request log for rate limits."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from .models import Transcript

_SCHEMA = """
CREATE TABLE IF NOT EXISTS transcripts (
    shortcode  TEXT PRIMARY KEY,
    payload    TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
    requester  TEXT NOT NULL,
    ts         REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS requests_by_user ON requests (requester, ts);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(_SCHEMA)
        self._lock = threading.Lock()

    # cache
    def get_transcript(self, shortcode: str) -> Optional[Transcript]:
        with self._lock:
            row = self._db.execute(
                "SELECT payload FROM transcripts WHERE shortcode = ?", (shortcode,)
            ).fetchone()
        return Transcript.from_dict(json.loads(row[0])) if row else None

    def put_transcript(self, t: Transcript) -> None:
        payload = t.to_dict()
        payload["cached"] = False
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO transcripts (shortcode, payload, created_at) VALUES (?, ?, ?)",
                (t.shortcode, json.dumps(payload, ensure_ascii=False), time.time()),
            )

    # rate limit log
    def count_requests(self, requester: str, since: float) -> int:
        with self._lock:
            return self._db.execute(
                "SELECT COUNT(*) FROM requests WHERE requester = ? AND ts >= ?", (requester, since)
            ).fetchone()[0]

    def oldest_request(self, requester: str, since: float) -> Optional[float]:
        with self._lock:
            row = self._db.execute(
                "SELECT MIN(ts) FROM requests WHERE requester = ? AND ts >= ?", (requester, since)
            ).fetchone()
        return row[0] if row and row[0] is not None else None

    def add_request(self, requester: str, ts: float) -> None:
        with self._lock:
            self._db.execute("INSERT INTO requests (requester, ts) VALUES (?, ?)", (requester, ts))
            # keep the table small: nothing older than two days matters
            self._db.execute("DELETE FROM requests WHERE ts < ?", (ts - 2 * 86400,))

    def stats(self) -> dict:
        with self._lock:
            n = self._db.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
            day = self._db.execute(
                "SELECT COUNT(*) FROM requests WHERE ts >= ?", (time.time() - 86400,)
            ).fetchone()[0]
        return {"cached_transcripts": n, "paid_requests_24h": day}
