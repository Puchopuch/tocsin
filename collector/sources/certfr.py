"""CERT-FR alerts (B4): the alerts of the last 7 days and the CVE numbers they cite, read in the
feed and, when robots.txt allows it, in the cve.org links of each alert page (the feed shortens
descriptions, so it may miss some)."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from .. import config
from ..models import CertfrAlert, host_is, is_safe_url
from . import Fetcher, SourceError, window_start

NAME = "CERT-FR, alertes"
NUMBER = re.compile(r"CERTFR-\d{4}-ALE-\d{3,}")
CVE = re.compile(r"CVE-\d{4}-\d{4,7}")
CVE_LINK = re.compile(r"cve\.org/CVERecord\?id=(CVE-\d{4}-\d{4,7})")
log = logging.getLogger(__name__)


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def parse(body: bytes) -> list[CertfrAlert]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        raise SourceError("CERT-FR : flux illisible") from None
    alerts = []
    for item in root.iter("item"):
        title = " ".join((item.findtext("title") or "").split())
        url = (item.findtext("link") or "").strip()
        number = NUMBER.search(url) or NUMBER.search(item.findtext("guid") or "")
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
        except (TypeError, ValueError, IndexError):
            continue
        if not (title and number) or not is_safe_url(url) or not host_is(url, config.CERTFR_HOST):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        alerts.append(CertfrAlert(
            number=number.group(0),
            title=title,
            url=url,
            published=published.astimezone(timezone.utc),
            cves=unique(CVE.findall(item.findtext("description") or "")),
        ))
    return alerts


def recent(alerts: list[CertfrAlert], now: datetime) -> list[CertfrAlert]:
    start = window_start(now)
    return [alert for alert in alerts if alert.published >= start]


def fetch(fetcher: Fetcher) -> list[CertfrAlert]:
    return parse(fetcher.get(config.CERTFR_FEED_URL))


class Robots:
    """robots.txt of each site, read once. When it cannot be read, its pages are not read."""

    def __init__(self, fetcher: Fetcher) -> None:
        self._fetcher = fetcher
        self._rules: dict[str, RobotFileParser | None] = {}

    def allows(self, url: str) -> bool:
        parts = urlsplit(url)
        site = f"{parts.scheme}://{parts.netloc}"
        if site not in self._rules:
            rules: RobotFileParser | None = RobotFileParser()
            try:
                text = self._fetcher.get(f"{site}/robots.txt").decode("utf-8", "replace")
                rules.parse(text.splitlines())
            except SourceError:
                rules = None
            self._rules[site] = rules
        rules = self._rules[site]
        return rules is not None and rules.can_fetch(config.USER_AGENT, url)


def with_page_cves(fetcher: Fetcher, alerts: list[CertfrAlert]) -> list[CertfrAlert]:
    """The alerts, with the CVE numbers that their page links to cve.org added."""
    robots = Robots(fetcher)
    result = []
    for alert in alerts:
        cves = list(alert.cves)
        if robots.allows(alert.url):
            try:
                page = fetcher.get(alert.url).decode("utf-8", "replace")
                cves += CVE_LINK.findall(page)
            except SourceError as error:
                log.warning("CERT-FR : page de l'alerte %s illisible (%s)", alert.number, error)
        result.append(alert.model_copy(update={"cves": unique(cves)}))
    return result
