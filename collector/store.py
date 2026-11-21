"""Persistent state in SQLite (collector/state.db, ignored by Git). Phase 1 keeps the HTTP
validators (ETag, Last-Modified) and the body of each source, so that a file that has not changed
is not downloaded again (B4). Phase 3 adds seen items, facts and cards.

Every query is written with placeholders (?), never by joining strings: a value can never become
SQL. state.db is only a cache: when it is missing or damaged, it starts again empty, and the next
collection gives the same cards."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Cached:
    etag: str | None
    last_modified: str | None
    body: bytes


def connect(path: Path | str) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    try:
        db.execute(
            "CREATE TABLE IF NOT EXISTS http_cache (url TEXT PRIMARY KEY, etag TEXT, "
            "last_modified TEXT, body BLOB NOT NULL, fetched_at TEXT NOT NULL)"
        )
        # The answers of the AI, by fingerprint of what was sent: the same article never costs a
        # second call. Kept 30 days.
        db.execute(
            "CREATE TABLE IF NOT EXISTS ai_cache (fingerprint TEXT PRIMARY KEY, answer TEXT NOT NULL, "
            "created_at TEXT NOT NULL)"
        )
        db.execute("DELETE FROM ai_cache WHERE created_at < datetime('now', '-30 days')")
        db.commit()
    except sqlite3.DatabaseError:
        db.close()
        raise
    return db


class Store:
    def __init__(self, path: Path | str) -> None:
        if isinstance(path, Path):
            path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._db = connect(path)
        except sqlite3.DatabaseError:
            if not isinstance(path, Path):
                raise
            log.warning("state.db illisible : remplacé par un cache vide")
            for name in (path.name, f"{path.name}-journal", f"{path.name}-wal", f"{path.name}-shm"):
                path.with_name(name).unlink(missing_ok=True)
            self._db = connect(path)

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._db.close()

    def cached(self, url: str) -> Cached | None:
        row = self._db.execute(
            "SELECT etag, last_modified, body FROM http_cache WHERE url = ?", (url,)
        ).fetchone()
        return Cached(row[0], row[1], bytes(row[2])) if row else None

    def answer(self, fingerprint: str) -> str | None:
        row = self._db.execute("SELECT answer FROM ai_cache WHERE fingerprint = ?", (fingerprint,)).fetchone()
        return row[0] if row else None

    def keep_answer(self, fingerprint: str, answer: str) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO ai_cache (fingerprint, answer, created_at) VALUES (?, ?, datetime('now'))",
            (fingerprint, answer),
        )
        self._db.commit()

    def save(self, url: str, etag: str | None, last_modified: str | None, body: bytes) -> None:
        if not etag and not last_modified:
            return  # nothing to send next time, so no use keeping the body
        self._db.execute(
            "INSERT OR REPLACE INTO http_cache (url, etag, last_modified, body, fetched_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (url, etag, last_modified, body, datetime.now(timezone.utc).isoformat()),
        )
        self._db.commit()
