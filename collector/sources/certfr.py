"""CERT-FR alerts (B4): the alerts of the last 7 days and the CVE numbers they cite, read in the
feed and, when robots.txt allows it, in each alert page: its cve.org links (the feed shortens
descriptions, so it may miss some) and its lists "Systèmes affectés" and "Risques".

The feed is read with defusedxml and no DTD at all: no entity, no external file, so neither an
XXE nor a "billion laughs" can go through. A broken item is skipped and counted."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

from .. import config
from ..models import CertfrAlert, host_is, is_safe_url
from ..text import BrokenText, clean, fold
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
        root = fromstring(body, forbid_dtd=True)
    except (ParseError, DefusedXmlException, ValueError, RecursionError):
        raise SourceError("CERT-FR : flux illisible") from None
    alerts, broken = [], 0
    for item in root.iter("item"):
        # A link is never cleaned: anything but plain ASCII makes is_safe_url refuse it.
        url = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "")[: config.MAX_URL]
        try:
            title = clean(item.findtext("title"), config.MAX_NAME)
            published = parsedate_to_datetime(clean(item.findtext("pubDate"), 100))
        except (BrokenText, TypeError, ValueError, IndexError):
            broken += 1
            continue
        number = NUMBER.search(url) or NUMBER.search(guid)
        if not (title and number) or not is_safe_url(url) or not host_is(url, config.CERTFR_HOST):
            broken += 1
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
    if broken:
        log.warning("CERT-FR : %d alerte(s) illisible(s) ignorée(s)", broken)
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


class Lists(HTMLParser):
    """The items of the lists under the headings "Risque(s)" and "Systèmes affectés" of an alert
    page. Only the text of the items is kept: no attribute, no comment, no script."""

    SECTIONS = {"risque": "risks", "risques": "risks", "systemes affectes": "systems"}
    MAX_ITEMS = 30

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: dict[str, list[str]] = {"risks": [], "systems": []}
        self._heading: list[str] | None = None
        self._section: str | None = None
        self._item: list[str] | None = None
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "template"):
            self._skip += 1
        elif tag in ("h1", "h2", "h3", "h4"):
            self._heading, self._section = [], None
        elif tag == "li" and self._section and self._item is None:
            self._item = []

    def handle_endtag(self, tag):
        if tag in ("script", "style", "template"):
            self._skip = max(0, self._skip - 1)
        elif tag in ("h1", "h2", "h3", "h4") and self._heading is not None:
            self._section = self.SECTIONS.get(fold(" ".join("".join(self._heading).split())))
            self._heading = None
        elif tag == "li" and self._item is not None:
            items = self.found[self._section]
            if len(items) < self.MAX_ITEMS:
                items.append("".join(self._item))
            self._item = None

    def handle_data(self, data):
        if self._skip:
            return
        if self._heading is not None:
            self._heading.append(data)
        elif self._item is not None:
            self._item.append(data)


def page_details(page: str) -> tuple[list[str], list[str], list[str]]:
    """The CVE numbers linked to cve.org, and the lists "Systèmes affectés" and "Risques" of an
    alert page. A broken item is skipped; a broken page gives empty lists."""
    lists = Lists()
    try:
        lists.feed(page)
        lists.close()
    except (AssertionError, ValueError, RecursionError):
        pass
    kept = {}
    for key, items in lists.found.items():
        kept[key] = []
        for item in items:
            try:
                value = clean(item, config.MAX_NAME)
            except BrokenText:
                continue
            if value:
                kept[key].append(value)
    return CVE_LINK.findall(page), unique(kept["systems"]), unique(kept["risks"])


def with_page_details(fetcher: Fetcher, alerts: list[CertfrAlert]) -> list[CertfrAlert]:
    """The alerts, with what their page adds: CVE numbers linked to cve.org, affected systems and
    risks. When robots.txt forbids the page, or it cannot be read, the feed alone is used."""
    robots = Robots(fetcher)
    result = []
    for alert in alerts:
        cves, systems, risks = list(alert.cves), [], []
        if robots.allows(alert.url):
            try:
                page_cves, systems, risks = page_details(fetcher.get(alert.url).decode("utf-8", "replace"))
                cves += page_cves
            except SourceError as error:
                log.warning("CERT-FR : page de l'alerte %s illisible (%s)", alert.number, error)
        result.append(alert.model_copy(update={"cves": unique(cves), "systems": systems, "risks": risks}))
    return result
