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
-- one row per request from any interface; no transcript text, no captions
CREATE TABLE IF NOT EXISTS events (
    ts                 REAL NOT NULL,
    user_id            TEXT NOT NULL,
    reel_shortcode     TEXT,
    duration           REAL,
    processing_ms      INTEGER NOT NULL,
    cache_hit          INTEGER NOT NULL,
    instagram_provider TEXT,
    stt_provider       TEXT,
    stt_path           TEXT,
    success            INTEGER NOT NULL,
    error_type         TEXT
);
CREATE INDEX IF NOT EXISTS events_by_ts ON events (ts);
"""

EVENT_FIELDS = ("ts", "user_id", "reel_shortcode", "duration", "processing_ms", "cache_hit",
                "instagram_provider", "stt_provider", "stt_path", "success", "error_type")


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

    def count_all_requests(self, since: float) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM requests WHERE ts >= ?", (since,)).fetchone()[0]

    def add_event(self, **event) -> None:
        row = tuple(event.get(k) for k in EVENT_FIELDS)
        with self._lock:
            self._db.execute(
                f"INSERT INTO events ({', '.join(EVENT_FIELDS)}) VALUES ({', '.join('?' * len(EVENT_FIELDS))})", row
            )

    def events(self, since: float = 0.0) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                f"SELECT {', '.join(EVENT_FIELDS)} FROM events WHERE ts >= ? ORDER BY ts", (since,)
            ).fetchall()
        return [dict(zip(EVENT_FIELDS, r)) for r in rows]

    def stats(self, since: float) -> dict:
        """Summary of events since `since` (unix time)."""
        with self._lock:
            total, ok, cached, users, paid, avg_ms = self._db.execute(
                """SELECT COUNT(*), COALESCE(SUM(success), 0), COALESCE(SUM(cache_hit), 0),
                          COUNT(DISTINCT user_id),
                          COALESCE(SUM(CASE WHEN success = 1 AND cache_hit = 0 THEN 1 ELSE 0 END), 0),
                          AVG(CASE WHEN success = 1 AND cache_hit = 0 THEN processing_ms END)
                   FROM events WHERE ts >= ?""", (since,)
            ).fetchone()
            errors = self._db.execute(
                "SELECT error_type, COUNT(*) FROM events WHERE ts >= ? AND success = 0 "
                "GROUP BY error_type ORDER BY 2 DESC", (since,)
            ).fetchall()
            cached_total = self._db.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
        return {"requests": total, "success": ok, "cache_hits": cached, "users": users,
                "paid": paid, "avg_paid_ms": int(avg_ms) if avg_ms else None,
                "errors": dict(errors), "cached_transcripts": cached_total}
