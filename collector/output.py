"""Validation and writing of cards.json (B10). Each card is checked against Card; the attacks of
the last 7 days are written newest first, with the time of the collection in UTC, through a
temporary file and a rename; and a full file is never replaced by an empty one (B5 rule 9)."""

from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from .models import DAY, Card, Feed
from .sources import window_start


def reason(error: ValidationError) -> str:
    """Why a card was refused, without repeating its content."""
    parts = []
    for item in error.errors(include_url=False, include_input=False, include_context=False):
        where = ".".join(str(part) for part in item["loc"]) or "carte"
        parts.append(f"{where} : {item['msg']}")
    return " ; ".join(parts)


def when(value: str) -> datetime:
    """first_seen as a UTC moment; a day alone counts from its start."""
    if DAY.fullmatch(value):
        return datetime.combine(date.fromisoformat(value), datetime.min.time(), timezone.utc)
    return datetime.fromisoformat(value)


def check(cards: list[dict]) -> tuple[list[dict], list[tuple[str, str]]]:
    """The valid cards, and the refused ones as (id, reason)."""
    valid, rejected = [], []
    for card in cards:
        try:
            valid.append(Card.model_validate(card).model_dump(mode="json"))
        except ValidationError as error:
            rejected.append((str(card.get("id", "?")), reason(error)))
    return valid, rejected


def newest_first(card: dict) -> tuple:
    """Sort key, in reverse: the newest day first; on the same day, a flaw already exploited before
    one that is not; then the latest time."""
    moment = when(card["first_seen"])
    return (moment.date(), bool(card.get("exploited")), moment)


def feed(cards: list[dict], now: datetime) -> dict:
    start = window_start(now)
    attacks = sorted(
        (card for card in cards if when(card["first_seen"]) >= start),
        key=newest_first,
        reverse=True,
    )
    data = {"generated_at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "attacks": attacks}
    Feed.model_validate(data)
    return data


def attacks_in(path: Path) -> int:
    """Number of attacks in the current file; 0 when it is missing or unreadable."""
    try:
        return len(json.loads(path.read_text(encoding="utf-8"))["attacks"])
    except (OSError, ValueError, KeyError, TypeError):
        return 0


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        for attempt in range(10):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:  # Windows: the site is reading the file at that moment
                if attempt == 9:
                    raise
                time.sleep(0.2)
    finally:
        temporary.unlink(missing_ok=True)


def publish(
    path: Path, cards: list[dict], now: datetime, *, sources_ok: int, dry_run: bool = False
) -> tuple[str, dict | None]:
    """Write cards.json, unless that would empty the site (B5 rule 9). Returns what happened, and
    the data written or that would have been written."""
    if sources_ok == 0:
        return "gardé tel quel : toutes les sources ont échoué", None
    data = feed(cards, now)
    previous = attacks_in(path)
    if not data["attacks"] and previous:
        return f"gardé tel quel : aucune carte, alors qu'il en contient {previous}", data
    if dry_run:
        return "rien d'écrit (--dry-run)", data
    write(path, data)
    return "écrit", data
