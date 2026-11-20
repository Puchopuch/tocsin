"""Polite access to the sources (B4): a User-Agent naming the project, 20 s at most per request,
at most one request per second to the same site, and ETag / Last-Modified so that a file that has
not changed is not downloaded again."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import httpx

from .. import config
from ..store import Store


class SourceError(Exception):
    """A source could not be read. The message names the site and the HTTP status, never a key."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def window_start(now: datetime) -> datetime:
    """Start of the 7-day window: midnight UTC, 7 days ago. Whole days, so that a source giving
    only a date counts the same way as a source giving a time."""
    day = (now.astimezone(timezone.utc) - timedelta(days=config.WINDOW_DAYS)).date()
    return datetime.combine(day, datetime.min.time(), timezone.utc)


class Fetcher:
    def __init__(
        self,
        store: Store | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.TIMEOUT_SECONDS,
            follow_redirects=True,
            transport=transport,
        )
        self._store = store
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, float] = {}
        self.requests = 0

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _pause(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            wait = config.SECONDS_BETWEEN_REQUESTS - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._last[host] = self._clock()

    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        cache: bool = True,
    ) -> bytes:
        target = httpx.URL(url, params=params)
        cached = self._store.cached(str(target)) if cache and self._store else None
        sent = dict(headers or {})
        if cached is not None:
            if cached.etag:
                sent["If-None-Match"] = cached.etag
            if cached.last_modified:
                sent["If-Modified-Since"] = cached.last_modified
        self._pause(target.host)
        try:
            response = self._client.get(target, headers=sent)
        except httpx.HTTPError as error:
            # Only the kind of error: its details could repeat the request and its headers.
            raise SourceError(f"{target.host} : {type(error).__name__}") from None
        self.requests += 1
        if response.status_code == 304 and cached is not None:
            return cached.body
        if response.status_code >= 400:
            raise SourceError(f"{target.host} : HTTP {response.status_code}", response.status_code)
        if cache and self._store:
            self._store.save(
                str(target),
                response.headers.get("ETag"),
                response.headers.get("Last-Modified"),
                response.content,
            )
        return response.content
