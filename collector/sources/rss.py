"""Feeds of the specialised press (phase 2, B4 and B7): the articles of the last 7 days that speak
of an attack, newest first. Read with defusedxml and no DTD, like the CERT-FR feed. Each link must
lead to the site of its feed. The text of an article is read on its page when robots.txt allows
it, visible text only; otherwise the summary of the feed is used."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring

from .. import config
from ..article import visible_text
from ..models import Article, host_is, is_safe_url
from ..text import BrokenText, clean, fold
from . import Fetcher, SourceError, window_start
from .certfr import Robots

ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"
log = logging.getLogger(__name__)


def when(value: str | None) -> datetime | None:
    value = (value or "").strip()[:80]
    if not value:
        return None
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def parse(body: bytes, site: str, lang: str) -> list[Article]:
    """The articles of a feed, RSS 2.0 or Atom. A broken item is skipped and counted."""
    try:
        root = fromstring(body, forbid_dtd=True)
    except (ParseError, DefusedXmlException, ValueError, RecursionError):
        raise SourceError(f"{site} : flux illisible") from None
    found = []
    for item in root.iter("item"):
        found.append((item.findtext("link"), item.findtext("title"), item.findtext("pubDate") or item.findtext(f"{DC}date"),
                      item.findtext("description")))
    for entry in root.iter(f"{ATOM}entry"):
        links = entry.findall(f"{ATOM}link")
        link = next((element.get("href") for element in links if element.get("rel", "alternate") == "alternate"), None)
        found.append((link, entry.findtext(f"{ATOM}title"), entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated"),
                      entry.findtext(f"{ATOM}summary") or entry.findtext(f"{ATOM}content")))
    articles, broken = [], 0
    domain = config.SOURCE_DOMAINS[site]
    for link, title, date, description in found:
        url = (link or "").strip()
        published = when(date)
        try:
            title = clean(title, 500)
            summary = clean(visible_text(description or "", 3_000), 3_000)
        except BrokenText:
            broken += 1
            continue
        if not (title and published and is_safe_url(url) and host_is(url, domain)):
            broken += 1
            continue
        articles.append(Article(site=site, url=url, title=title, published=published, summary=summary, lang=lang))
    if broken:
        log.warning("%s : %d article(s) illisible(s) ignoré(s)", site, broken)
    return articles


def about_an_attack(article: Article) -> bool:
    """B7 step 1, without AI: a word of the field in the title or the summary."""
    text = fold(f"{article.title} {article.summary}")
    return any(fold(word) in text for word in config.DOMAIN_WORDS)


def recent(articles: list[Article], now: datetime) -> list[Article]:
    """The articles of the last 7 days that speak of an attack, newest first, each link once."""
    start = window_start(now)
    seen, kept = set(), []
    for article in sorted(articles, key=lambda a: a.published, reverse=True):
        if start <= article.published <= now and article.url not in seen and about_an_attack(article):
            seen.add(article.url)
            kept.append(article)
    return kept


def fetch(fetcher: Fetcher, now: datetime) -> tuple[list[Article], list[tuple[str, str, str]]]:
    """The recent articles of every feed, and per feed (name, "ok" or "échec", detail)."""
    articles, reports = [], []
    for site, url, lang in config.PRESS_FEEDS:
        try:
            read = parse(fetcher.get(url), site, lang)
        except SourceError as error:
            reports.append((site, "échec", str(error)))
            continue
        kept = recent(read, now)
        articles += kept
        reports.append((site, "ok", f"{len(read)} articles lus, {len(kept)} sur une attaque ces 7 derniers jours"))
    return sorted(articles, key=lambda a: a.published, reverse=True), reports


def text_of(fetcher: Fetcher, robots: Robots, article: Article) -> str:
    """What the AI may read of an article: its title and visible text, from its page when
    robots.txt allows it and it says enough, else the summary of the feed; cut to
    MAX_ARTICLE_CHARS."""
    body = ""
    if robots.allows(article.url):
        try:
            body = visible_text(fetcher.get(article.url).decode("utf-8", "replace"))
        except SourceError as error:
            log.warning("%s : article illisible (%s)", article.site, error)
    if len(body) < config.MIN_ARTICLE_CHARS:
        body = article.summary
    return f"{article.title}\n\n{body}"[: config.MAX_ARTICLE_CHARS]
