"""Cards from press articles (phase 2, B7): the AI reads, the code judges.

For each recent article about an attack, newest first, while the budget lasts:
1. the AI extracts facts, each with a quote; collector/facts.py keeps only what the article proves;
2. the code decides the level, the statuses, the audience, the links and the dates;
3. the AI writes the texts of the card, in French and in English, from the facts kept only, never
   from the article. The code checks the lengths (one more try when too long) and refuses any
   link, e-mail, phone number, IBAN, wallet address or number that is not in the facts.
A victim whose name may be a person's is held back, like the claims of phase 1.

With the budget left, the AI also translates into French the text of the CISA for its cards,
without adding anything; the English stays the text of the CISA.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import Field

from . import config
from .ai import AiError, Mistral, prompt, prompts_version
from .cards import fitting, looks_like_person, moment, text, unknown_attacker
from .facts import Facts, Strict, Verified, level, numbers_in, verify
from .models import EMAIL, PHONE, Article, KevEntry
from .sources import Fetcher, rss
from .sources.certfr import Robots
from .text import BrokenText, clean

log = logging.getLogger(__name__)


class Pair(Strict):
    fr: str = Field(min_length=1, max_length=config.MAX_TEXT)
    en: str = Field(min_length=1, max_length=config.MAX_TEXT)


class CardTexts(Strict):
    """The answer of the second call: the texts of a card, nothing else."""

    title: Pair
    method: Pair | None
    loot: Pair | None
    am_i_affected: Pair
    action: Pair | None
    summary: list[Pair] = Field(min_length=1, max_length=3)
    protection_steps: list[Pair] = Field(max_length=4)


class Translation(Strict):
    summary: str = Field(min_length=1, max_length=config.MAX_TEXT)
    action: str = Field(max_length=config.MAX_TEXT)


class Rejected(Exception):
    """A card whose texts break a rule: it is not published, and the reason goes to the journal."""


LINK = re.compile(r"https?:|www\.|\b[\w-]+\.(?:com|org|net|fr|eu|io|ru|cn|su|onion|info|biz|xyz|top|me|ly|to)\b|\[\.\]|hxxp", re.IGNORECASE)
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ -]?[A-Z0-9]{4}){2,7}(?:[ -]?[A-Z0-9]{1,4})?\b")
WALLET = re.compile(
    r"\b(?:bc1[ac-hj-np-z02-9]{20,80}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}|0x[a-fA-F0-9]{40}"
    r"|4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}|T[1-9A-HJ-NP-Za-km-z]{33})\b"
)
LIMITS = {"method": config.MAX_SHORT, "loot": config.MAX_SHORT, "am_i_affected": config.MAX_LINE, "action": config.MAX_LINE}


def forbidden(value: str) -> str | None:
    """What a text written by the AI must never hold."""
    if LINK.search(value):
        return "lien ou adresse web"
    if EMAIL.search(value) or PHONE.search(value):
        return "e-mail ou numéro de téléphone"
    if IBAN.search(value) or WALLET.search(value):
        return "IBAN ou adresse de portefeuille"
    return None


def tidy(texts: CardTexts) -> CardTexts:
    """The texts cleaned like those of a source: hidden characters out, spaces collapsed, NFC."""
    def one(pair: Pair | None) -> Pair | None:
        if pair is None:
            return None
        try:
            return Pair(fr=clean(pair.fr, config.MAX_TEXT), en=clean(pair.en, config.MAX_TEXT))
        except (BrokenText, ValueError):
            raise Rejected("texte illisible") from None

    return CardTexts(
        title=one(texts.title), method=one(texts.method), loot=one(texts.loot), am_i_affected=one(texts.am_i_affected),
        action=one(texts.action), summary=[one(p) for p in texts.summary], protection_steps=[one(p) for p in texts.protection_steps],
    )


def problems(texts: CardTexts, facts: Verified) -> list[str]:
    allowed = facts.numbers()
    found = []
    named = [("title", texts.title), ("method", texts.method), ("loot", texts.loot),
             ("am_i_affected", texts.am_i_affected), ("action", texts.action)]
    named += [("summary", pair) for pair in texts.summary] + [("protection_steps", pair) for pair in texts.protection_steps]
    for name, pair in named:
        if pair is None:
            continue
        for lang in ("fr", "en"):
            value = getattr(pair, lang)
            if name == "title" and len(value.split()) > config.MAX_TITLE_WORDS:
                found.append(f"longueur de {name}")
            elif name in LIMITS and len(value) > LIMITS[name]:
                found.append(f"longueur de {name}")
            if (reason := forbidden(value)) is not None:
                found.append(f"{reason} dans {name}")
            if numbers_in(value) - allowed:
                found.append(f"chiffre absent des faits dans {name}")
    return sorted(set(found))


def write_texts(ai: Mistral, facts: Verified) -> CardTexts:
    """The texts of the card, written from the facts kept. Too long: one more try (B5 rule 5)."""
    data = json.dumps(facts.for_writing(), ensure_ascii=False)
    texts = tidy(ai.ask("carte", prompt("card"), data, CardTexts))
    issues = problems(texts, facts)
    if issues and all(issue.startswith("longueur") for issue in issues):
        texts = tidy(ai.ask("carte_plus_courte", f"{prompt('card')}\n\n{prompt('shorter')}", data, CardTexts))
        issues = problems(texts, facts)
    if issues:
        raise Rejected(" ; ".join(issues))
    return texts


def press_card(article: Article, facts: Verified, texts: CardTexts, ai: dict) -> dict:
    """The card: its texts come from the AI, everything else from the code."""
    severity, reason = level(facts)
    name = facts.attacker or facts.claimed_by
    if name or facts.country:
        attacker = {
            "name": text(name, name) if name else text("Attaquant non nommé", "Unnamed attacker"),
            "country": text(facts.country, facts.country) if facts.country else None,
            "status": "revendique" if facts.claimed_by else ("confirme" if facts.authority else "presume"),
            "source": facts.authority if facts.country else None,
        }
    else:
        attacker = unknown_attacker()
    timeline = [{"date": moment(article.published), "label": text(f"Article de {article.site}", f"{article.site} article")}]
    if facts.attack_date:
        timeline.insert(0, {"date": facts.attack_date, "label": text("Attaque, selon l'article", "Attack, according to the article")})

    def pair(value: Pair | None) -> dict | None:
        return text(value.fr, value.en) if value else None

    return {
        "id": "press-" + hashlib.sha256(article.url.encode()).hexdigest()[:12],
        "severity": severity,
        "severity_reason": reason,
        "title": pair(texts.title),
        "first_seen": moment(article.published),
        "audience": "les_deux" if (facts.people or facts.sensitive or facts.data_types) else "entreprises",
        "reliability": "confirme",
        "reliability_source": None,
        "exploited": False,
        "kind": "faille" if facts.kind == "faille_exploitee" else "attaque",
        "attacker": attacker,
        "victim": {
            "label": fitting([(facts.victim, facts.victim), ("Organisation citée par l'article", "Organisation named in the article")], config.MAX_SHORT),
            "status": "confirme" if facts.confirmed_by else ("revendique" if facts.claimed_by else "presume"),
        },
        "method": pair(texts.method),
        "loot": pair(texts.loot),
        "am_i_affected": pair(texts.am_i_affected),
        "action": pair(texts.action) or text(
            "Méfiez-vous des messages qui citent cette organisation.",
            "Be wary of messages that mention this organisation.",
        ),
        "summary": [pair(value) for value in texts.summary],
        "timeline": sorted(timeline, key=lambda event: event["date"]),
        "protection_steps": [pair(value) for value in texts.protection_steps],
        "technical": {"cves": facts.cves, "software": [], "techniques": []},
        "sources": [{"name": article.site, "title": text(article.title, article.title), "url": article.url, "official": False}],
        "ai": ai,
    }


def translate(ai: Mistral, card: dict, entry: KevEntry) -> dict:
    """A CISA card with the text of the CISA translated into French by the AI, without adding
    anything: no number, link or address that the text of the CISA does not hold."""
    if not entry.description or len(entry.description) > config.MAX_TEXT or len(entry.required_action) > config.MAX_TEXT:
        return card
    source = f"description : {entry.description}\naction : {entry.required_action}"
    answer = ai.ask("traduction_cisa", prompt("translation"), source, Translation)
    try:
        summary, action = clean(answer.summary, config.MAX_TEXT), clean(answer.action, config.MAX_TEXT)
    except BrokenText:
        raise Rejected("traduction illisible") from None
    for value in (summary, action):
        reason = forbidden(value)
        if reason and not (reason == "lien ou adresse web" and LINK.search(source)):
            raise Rejected(f"{reason} dans la traduction")
        if numbers_in(value) - numbers_in(source):
            raise Rejected("chiffre absent du texte de la CISA dans la traduction")
    translated = {**card, "summary": [*card["summary"], text(summary, entry.description)]}
    if entry.required_action and action:
        translated["protection_steps"] = [*card["protection_steps"], text(action, entry.required_action)]
    translated["ai"] = {"role": "traduction", "model": ai.model, "prompts": prompts_version()}
    return translated


@dataclass
class Press:
    """What phase 2 did in a run."""

    cards: list[dict] = field(default_factory=list)
    held: list[tuple[str, str]] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)
    feeds: list[tuple[str, str, str]] = field(default_factory=list)
    articles: int = 0
    not_incidents: int = 0
    translated: int = 0
    stopped: str | None = None  # why the AI stopped before the end, when it is a failure
    budget_reached: bool = False


def read(fetcher: Fetcher, ai: Mistral, now: datetime, entries: dict[str, KevEntry], cards: list[dict]) -> Press:
    """Phase 2: the press cards, then the CISA cards translated, while the budget lasts. The CISA
    cards of `cards` are translated in place, newest first."""
    result = Press()
    articles, result.feeds = rss.fetch(fetcher, now)
    result.articles = len(articles)
    robots = Robots(fetcher)
    written = {"role": "redaction", "model": ai.model, "prompts": prompts_version()}
    for article in articles:
        try:
            body = rss.text_of(fetcher, robots, article)
            facts = verify(ai.ask("faits", prompt("facts"), body, Facts), body)
            if facts is None:
                result.not_incidents += 1
                continue
            if looks_like_person(facts.victim):
                result.held.append(("nom qui ressemble à celui d'une personne", f"{article.site} / {facts.victim}"))
                continue
            result.cards.append(press_card(article, facts, write_texts(ai, facts), written))
        except Rejected as error:
            result.rejected.append((f"{article.site} {article.published:%Y-%m-%d}", str(error)))
        except AiError as error:
            if error.reason == "reponse_invalide":
                result.rejected.append((f"{article.site} {article.published:%Y-%m-%d}", str(error)))
                continue
            if error.reason == "budget":
                result.budget_reached = True
            else:
                result.stopped = str(error)
            return result
    for index, card in enumerate(cards):
        entry = entries.get(card["id"].removeprefix("kev-")) if card["id"].startswith("kev-") else None
        if entry is None:
            continue
        try:
            cards[index] = translate(ai, card, entry)
            result.translated += cards[index] is not card
        except Rejected as error:
            result.rejected.append((card["id"], str(error)))
        except AiError as error:
            if error.reason == "budget":
                result.budget_reached = True
                break
            if error.reason != "reponse_invalide":
                result.stopped = str(error)
                break
    return result
