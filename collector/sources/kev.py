"""CISA catalogue of Known Exploited Vulnerabilities (B4): the flaws added in the last 7 days
(field dateAdded). A broken entry is skipped and counted; the rest of the catalogue is kept."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from .. import config
from ..models import KevEntry
from ..text import clean
from . import Fetcher, SourceError, window_start

NAME = "CISA, failles exploitées"
log = logging.getLogger(__name__)


def parse(body: bytes) -> list[KevEntry]:
    try:
        rows = json.loads(body)["vulnerabilities"]
    except (ValueError, KeyError, TypeError, RecursionError):
        raise SourceError("CISA : catalogue illisible") from None
    if not isinstance(rows, list):
        raise SourceError("CISA : catalogue illisible")
    entries, broken = [], 0
    for raw in rows:
        try:
            entries.append(KevEntry(
                cve=clean(raw["cveID"], 20),
                vendor=clean(raw["vendorProject"], config.MAX_NAME),
                product=clean(raw["product"], config.MAX_NAME),
                name=clean(raw.get("vulnerabilityName"), config.MAX_NAME),
                description=clean(raw.get("shortDescription"), config.MAX_DESCRIPTION),
                required_action=clean(raw.get("requiredAction"), config.MAX_DESCRIPTION),
                cwes=[clean(cwe, 20) for cwe in (raw.get("cwes") or [])[:20]],
                date_added=clean(raw["dateAdded"], 10),
                due_date=clean(raw.get("dueDate"), 10) or None,
                ransomware=clean(raw.get("knownRansomwareCampaignUse"), 20),
            ))
        except (KeyError, TypeError, AttributeError, ValueError):
            broken += 1  # ValueError covers BrokenText and the validation of KevEntry
    if broken:
        log.warning("CISA : %d entrée(s) illisible(s) ignorée(s)", broken)
    return entries


def recent(entries: list[KevEntry], now: datetime) -> list[KevEntry]:
    start = window_start(now).date()
    return [entry for entry in entries if entry.date_added >= start]


def fetch(fetcher: Fetcher) -> list[KevEntry]:
    return parse(fetcher.get(config.KEV_URL))
