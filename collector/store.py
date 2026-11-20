"""Persistent state in SQLite (collector/state.db, ignored by Git). Phase 1 keeps the HTTP
validators (ETag, Last-Modified) and the body of each source, so that a file that has not changed
is not downloaded again (B4). Phase 3 adds seen items, facts and cards."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Cached:
    etag: str | None
    last_modified: str | None
    body: bytes


class Store:
    def __init__(self, path: Path | str) -> None:
        if isinstance(path, Path):
            path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS http_cache (url TEXT PRIMARY KEY, etag TEXT, "
            "last_modified TEXT, body BLOB NOT NULL, fetched_at TEXT NOT NULL)"
        )
        self._db.commit()

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

    def save(self, url: str, etag: str | None, last_modified: str | None, body: bytes) -> None:
        if not etag and not last_modified:
            return  # nothing to send next time, so no use keeping the body
        self._db.execute(
            "INSERT OR REPLACE INTO http_cache (url, etag, last_modified, body, fetched_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (url, etag, last_modified, body, datetime.now(timezone.utc).isoformat()),
        )
        self._db.commit()
