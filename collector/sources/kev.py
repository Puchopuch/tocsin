"""CISA catalogue of Known Exploited Vulnerabilities (B4): the flaws added in the last 7 days
(field dateAdded)."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from pydantic import ValidationError

from .. import config
from ..models import KevEntry
from . import Fetcher, SourceError, window_start

NAME = "CISA, failles exploitées"
log = logging.getLogger(__name__)


def parse(body: bytes) -> list[KevEntry]:
    try:
        rows = json.loads(body)["vulnerabilities"]
    except (ValueError, KeyError, TypeError):
        raise SourceError("CISA : catalogue illisible") from None
    entries = []
    for raw in rows:
        try:
            entries.append(KevEntry(
                cve=raw["cveID"],
                vendor=raw["vendorProject"].strip(),
                product=raw["product"].strip(),
                name=raw.get("vulnerabilityName") or "",
                description=raw.get("shortDescription") or "",
                date_added=raw["dateAdded"],
                due_date=raw.get("dueDate") or None,
                ransomware=raw.get("knownRansomwareCampaignUse") or "",
            ))
        except (KeyError, TypeError, AttributeError, ValidationError):
            log.warning("CISA : entrée illisible ignorée")
    return entries


def recent(entries: list[KevEntry], now: datetime) -> list[KevEntry]:
    start = window_start(now).date()
    return [entry for entry in entries if entry.date_added >= start]


def fetch(fetcher: Fetcher) -> list[KevEntry]:
    return parse(fetcher.get(config.KEV_URL))
