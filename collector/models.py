"""Pydantic models (B3): the entries read from each source, and the card of cards.json, which
follows frontend/README.md. The site reads exactly what Card accepts."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import config

Level = Literal["critique", "grave", "significative", "mineure"]
Audience = Literal["grand_public", "entreprises", "les_deux"]
Status = Literal["confirme", "revendique", "presume", "inconnu"]

DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
CVE = re.compile(r"CVE-\d{4}-\d{4,}")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<![\w+])(?:\+\d{2,3}[\s.-]?\d|0\d)(?:[\s.-]?\d{2}){4}(?!\d)")


def is_safe_url(url: str) -> bool:
    """http(s) only, with a host, never a .onion address, never a user name or a password."""
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
        credentials = parts.username is not None or parts.password is not None
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(host) and not host.endswith(".onion") and not credentials


def host_is(url: str, domain: str) -> bool:
    """True when the link points to this domain or to one of its subdomains."""
    try:
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return host == domain or host.endswith("." + domain)


def check_moment(value: str) -> str:
    """A day alone ("2026-11-18") when the source gives no time, otherwise a UTC date and time
    ending with Z ("2026-11-18T07:42:00Z"). Never a time that the source did not give."""
    if DAY.fullmatch(value):
        date.fromisoformat(value)
        return value
    moment = datetime.fromisoformat(value)
    if not value.endswith("Z") or moment.utcoffset() != timedelta(0):
        raise ValueError("date et heure attendues en UTC, terminées par Z")
    return value


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Entries read from the sources (the "Items" of B3), before they become cards.


class KevEntry(Model):
    """One entry of the CISA catalogue."""

    cve: str
    vendor: str
    product: str
    name: str = ""
    description: str = ""
    date_added: date
    due_date: date | None = None
    ransomware: str = ""


class CertfrAlert(Model):
    """One alert of the CERT-FR feed."""

    number: str
    title: str
    url: str
    published: datetime
    cves: list[str] = Field(default_factory=list)


class Claim(Model):
    """One ransomware claim recorded by ransomware.live. Only what a card shows is kept."""

    victim: str
    group: str
    country: str
    discovered: datetime | date
    permalink: str


# The card, as frontend/README.md describes it.


class Text(Model):
    """A text of the card, in French and in English. Both are required: the site never shows a
    missing text in one language."""

    fr: str = Field(min_length=1)
    en: str = Field(min_length=1)


LANGUAGES = {"fr": "en français", "en": "en anglais"}


def within(text: Text | None, limit: int) -> Text | None:
    """A length limit of frontend/README.md, in each language."""
    if text is not None:
        for lang, where in LANGUAGES.items():
            if len(getattr(text, lang)) > limit:
                raise ValueError(f"plus de {limit} caractères {where}")
    return text


class Attacker(Model):
    name: Text | None = None
    country: Text | None = None
    status: Status
    source: str | None = None

    @model_validator(mode="after")
    def _country_has_source(self) -> Attacker:
        # B5 rule 3: a country only when an authority or a major medium names it.
        if self.country and not self.source:
            raise ValueError("pays de l'attaquant sans source")
        return self


class Victim(Model):
    label: Text | None = None
    status: Status

    @field_validator("label")
    @classmethod
    def _label(cls, value: Text | None) -> Text | None:
        return within(value, config.MAX_SHORT)


class Event(Model):
    date: str
    label: Text

    @field_validator("date")
    @classmethod
    def _date(cls, value: str) -> str:
        return check_moment(value)


class Technique(Model):
    id: str = Field(min_length=1)
    name: str = ""


class Technical(Model):
    cves: list[str] = Field(default_factory=list)
    software: list[str] = Field(default_factory=list)
    techniques: list[Technique] = Field(default_factory=list)

    @field_validator("cves")
    @classmethod
    def _cves(cls, values: list[str]) -> list[str]:
        for value in values:
            if not CVE.fullmatch(value):
                raise ValueError(f"numéro de CVE invalide : {value}")
        return values


class Source(Model):
    name: str = Field(min_length=1)
    title: Text | None = None
    url: str
    official: bool = False

    @field_validator("url")
    @classmethod
    def _url(cls, value: str) -> str:
        if not is_safe_url(value):
            raise ValueError("lien refusé : http(s) seulement, jamais d'adresse .onion")
        return value


class Card(Model):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]*$")
    severity: Level
    severity_reason: Text
    title: Text
    first_seen: str
    audience: Audience
    reliability: Literal["confirme", "rumeur"]
    reliability_source: str | None = None
    # True only when a source confirms that the flaw is already exploited (the CISA catalogue).
    exploited: bool = False
    attacker: Attacker | None = None
    victim: Victim
    method: Text | None = None
    loot: Text | None = None
    am_i_affected: Text | None = None
    action: Text | None = None
    summary: list[Text] = Field(default_factory=list)
    timeline: list[Event] = Field(default_factory=list)
    protection_steps: list[Text] = Field(default_factory=list)
    technical: Technical = Field(default_factory=Technical)
    sources: list[Source] = Field(min_length=1)
    # Fields whose English text is the words of the source, kept as they are because translating
    # them would mean inventing.
    untranslated: list[Literal["title"]] = Field(default_factory=list)

    @field_validator("first_seen")
    @classmethod
    def _first_seen(cls, value: str) -> str:
        return check_moment(value)

    @field_validator("title")
    @classmethod
    def _title(cls, value: Text) -> Text:
        for lang, where in LANGUAGES.items():
            if len(getattr(value, lang).split()) > config.MAX_TITLE_WORDS:
                raise ValueError(f"titre de plus de {config.MAX_TITLE_WORDS} mots {where}")
        return value

    @field_validator("method", "loot")
    @classmethod
    def _short(cls, value: Text | None) -> Text | None:
        return within(value, config.MAX_SHORT)

    @field_validator("am_i_affected", "action")
    @classmethod
    def _line(cls, value: Text | None) -> Text | None:
        return within(value, config.MAX_LINE)

    @model_validator(mode="after")
    def _claims_stay_significant(self) -> Card:
        # B5 rule 4: a claim or a rumour is never above "significative".
        claimed = self.victim.status == "revendique" or (
            self.attacker is not None and self.attacker.status == "revendique"
        )
        if (claimed or self.reliability == "rumeur") and self.severity in ("critique", "grave"):
            raise ValueError("revendication ou rumeur au-dessus de « significative »")
        return self

    @model_validator(mode="after")
    def _no_personal_data(self) -> Card:
        # B5 rule 7: organisations only, never an e-mail address or a phone number.
        texts = [
            self.title, self.severity_reason, self.method, self.loot, self.am_i_affected,
            self.action, self.victim.label, self.attacker.name if self.attacker else None,
            *self.summary, *self.protection_steps, *(event.label for event in self.timeline),
        ]
        for text in filter(None, texts):
            for value in (text.fr, text.en):
                if EMAIL.search(value) or PHONE.search(value):
                    raise ValueError("donnée personnelle : adresse e-mail ou numéro de téléphone")
        return self


class Feed(Model):
    generated_at: str
    attacks: list[Card]

    @field_validator("generated_at")
    @classmethod
    def _generated_at(cls, value: str) -> str:
        if DAY.fullmatch(value):
            raise ValueError("l'heure de la collecte est attendue")
        return check_moment(value)
