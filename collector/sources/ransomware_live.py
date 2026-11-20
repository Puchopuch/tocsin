"""ransomware.live PRO API (B4): ransomware claims against organisations of the followed countries
(config.TRACKED_COUNTRIES), recorded in the last 7 days. The key is read from .env, held as a
SecretStr and sent in the X-API-KEY header to api-pro.ransomware.live only. Only the victim, the
country, the group, the date and the ransomware.live permalink are kept: the link to the group's
site (post_url), the screenshots, the infostealer data and everything else are dropped as soon as
the answer is read (B5 rule 2)."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone

import httpx
from dotenv import dotenv_values
from pydantic import SecretStr

from .. import config
from ..models import Claim, host_is, is_safe_url
from ..text import BrokenText, clean, fold
from . import ApiKey, Fetcher, SourceError, window_start

NAME = "ransomware.live, revendications"
COUNTRY = re.compile(r"[A-Z]{2}")


def api_key() -> ApiKey | None:
    """The key, from the environment (GitHub secrets) or from .env; None when empty. Never shown:
    it stays a SecretStr until the request is built."""
    value = os.environ.get(config.RANSOMWARE_LIVE_KEY)
    if not value and config.ENV_PATH.exists():
        value = dotenv_values(config.ENV_PATH).get(config.RANSOMWARE_LIVE_KEY)
    value = (value or "").strip()
    if not value:
        return None
    return ApiKey(header="X-API-KEY", host=httpx.URL(config.RANSOMWARE_LIVE_API).host, secret=SecretStr(value))


def explain(error: SourceError) -> str:
    if error.status in (401, 403):
        return f"clé refusée (HTTP {error.status})"
    if error.status == 429:
        return "trop de requêtes, réessayer plus tard (HTTP 429)"
    return str(error)


def months(now: datetime) -> list[tuple[int, int]]:
    """The months covered by the last 7 days: the API filters by year and month."""
    day = window_start(now).date().replace(day=1)
    result = []
    while day <= now.date():
        result.append((day.year, day.month))
        day = date(day.year + day.month // 12, day.month % 12 + 1, 1)
    return result


def moment(value: object) -> datetime | date | None:
    text = str(value or "").strip()
    if not text or len(text) > 40:
        return None
    try:
        if len(text) == 10:
            return date.fromisoformat(text)
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    # The API gives its times without a time zone: they are UTC.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def rows(data: object) -> list[dict]:
    if isinstance(data, dict):
        lists = (data[key] for key in ("victims", "data", "results") if isinstance(data.get(key), list))
        data = next(lists, [])
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def parse(body: bytes) -> list[Claim]:
    try:
        data = json.loads(body)
    except (ValueError, RecursionError):
        raise SourceError("ransomware.live : réponse illisible") from None
    claims = []
    for raw in rows(data):
        try:
            victim = clean(raw.get("victim"), config.MAX_NAME)
            group = clean(raw.get("group"), config.MAX_NAME)
            country = clean(raw.get("country"), 10).upper()
        except BrokenText:
            continue
        discovered = moment(raw.get("discovered"))
        permalink = raw.get("permalink")
        permalink = permalink.strip() if isinstance(permalink, str) else ""
        if not (victim and group and COUNTRY.fullmatch(country) and discovered):
            continue
        if not is_safe_url(permalink) or not host_is(permalink, config.RANSOMWARE_LIVE_HOST):
            continue  # a card needs its link to ransomware.live, never one to the group's site
        claims.append(Claim(
            victim=victim, group=group, country=country, discovered=discovered, permalink=permalink,
        ))
    return claims


def recent(claims: list[Claim], now: datetime) -> list[Claim]:
    """Claims of the followed countries in the last 7 days, each victim of a group once."""
    start = window_start(now)
    kept, seen = [], set()
    for claim in claims:
        found = claim.discovered
        if not isinstance(found, datetime):
            found = datetime.combine(found, datetime.min.time(), timezone.utc)
        key = (fold(claim.group), fold(claim.victim))
        if claim.country in config.TRACKED_COUNTRIES and found >= start and key not in seen:
            seen.add(key)
            kept.append(claim)
    return kept


def fetch(fetcher: Fetcher, now: datetime, key: ApiKey) -> tuple[list[Claim], int]:
    """Claims of the followed countries over the last 7 days, and the number of entries read."""
    read: list[Claim] = []
    for country in config.TRACKED_COUNTRIES:
        for year, month in months(now):
            body = fetcher.get(
                f"{config.RANSOMWARE_LIVE_API}/victims/",
                params={"country": country, "year": str(year), "month": f"{month:02d}"},
                key=key,
            )
            read += parse(body)
    return recent(read, now), len(read)
