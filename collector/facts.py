"""What a press article establishes (phase 2, B7 step 3, and B8).

The AI extracts facts, each with a quote of the article (25 words at most). The code keeps a fact
only when its quote is in the article word for word, after normalising spaces, apostrophes, quotes
and dashes (never approximately), and says what the fact says: the name is in the quote, the number
is in the quote, a fact that raises the level holds a word of its kind. An attacker's country is
kept only when the quote names an authority of the closed list (config.AUTHORITIES). The level is
then computed by the code from the facts kept: what the AI says about the level counts for nothing.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from . import config
from .models import CVE
from .text import fold

Kind = Literal["fuite_de_donnees", "rancongiciel", "faille_exploitee", "deni_de_service", "hameconnage", "autre"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Quoted(Strict):
    value: str | None = Field(max_length=300)
    quote: str | None = Field(max_length=400)


class QuotedNumber(Strict):
    value: int | None = Field(ge=0)
    quote: str | None = Field(max_length=400)


class QuotedFlag(Strict):
    value: bool
    quote: str | None = Field(max_length=400)


class Attribution(Strict):
    authority: str | None = Field(max_length=200)
    country: str | None = Field(max_length=100)
    quote: str | None = Field(max_length=400)


class Facts(Strict):
    """The answer of the first call to the AI. Any other field, or a missing one, is refused."""

    is_incident: bool
    type: Kind
    victim: Quoted
    sector: Quoted
    attacker: Quoted
    attribution: Attribution
    claimed_by: Quoted
    confirmed_by: Quoted
    people_affected: QuotedNumber
    sensitive_data: QuotedFlag
    data_types: list[Quoted] = Field(max_length=10)
    outage_days: QuotedNumber
    vital_services: QuotedFlag
    public_service_down: QuotedFlag
    supplier_attack: QuotedFlag
    national_impact: QuotedFlag
    cves: list[Quoted] = Field(max_length=20)
    attack_date: Quoted
    recommended_actions: list[Quoted] = Field(max_length=6)


def strict_schema(model: type[BaseModel]) -> dict:
    """The JSON schema of a model for the strict structured output of the AI: references inlined,
    every property required, no other property allowed."""
    schema = model.model_json_schema()
    definitions = schema.pop("$defs", {})

    def inline(node):
        if isinstance(node, list):
            return [inline(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return inline(definitions[node["$ref"].rsplit("/", 1)[-1]])
        node = {key: inline(value) for key, value in node.items() if key not in ("title", "description", "default")}
        if node.get("type") == "object":
            node["additionalProperties"] = False
            node["required"] = list(node.get("properties", {}))
        return node

    return inline(schema)


# Quotes ----------------------------------------------------------------------------------------

SAME_FORMS = str.maketrans({
    "’": "'", "‘": "'", "ʼ": "'", "`": "'", "´": "'", "′": "'",
    "“": '"', "”": '"', "«": '"', "»": '"', "„": '"', "‟": '"', "″": '"',
    "–": "-", "—": "-", "‐": "-", "‑": "-", "‒": "-", "−": "-",
    " ": " ", " ": " ", " ": " ",
})


def normal(text: str) -> str:
    """Spaces, apostrophes, quotes and dashes written one way; nothing else changes (case,
    accents and words stay as they are)."""
    text = " ".join(unicodedata.normalize("NFC", text).translate(SAME_FORMS).split())
    return re.sub(r'"\s+', '"', re.sub(r'\s+"', '"', text))


def quoted(quote: str | None, article: str) -> bool:
    """True when the quote is in the article word for word (after normal), with 3 to 25 words."""
    if not quote:
        return False
    words = len(quote.split())
    return 3 <= words <= config.MAX_QUOTE_WORDS and normal(quote) in article


def said_in(value: str | None, quote: str | None) -> bool:
    """True when the value is written in the quote (case and accents aside)."""
    return bool(value and quote and fold(normal(value)) in fold(normal(quote)))


NUMBER = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:[ .,]\d{3})+|\d+(?:[.,]\d+)?)\s*(millions?|milliards?|billions?|thousand|mille|k\b)?",
    re.IGNORECASE,
)
SCALES = {"million": 10**6, "millions": 10**6, "milliard": 10**9, "milliards": 10**9, "billion": 10**9,
          "billions": 10**9, "thousand": 10**3, "mille": 10**3, "k": 10**3}


def numbers_in(text: str) -> set[int]:
    """The numbers written in a text: "12 000", "12,000", "2,4 millions", "2.4 million"."""
    found = set()
    for match in NUMBER.finditer(normal(text)):
        digits, scale = match.group(1), (match.group(2) or "").lower()
        if scale:
            try:
                found.add(round(float(digits.replace(" ", "").replace(",", ".")) * SCALES[scale]))
            except ValueError:
                continue
        elif re.fullmatch(r"\d{1,3}(?:[ .,]\d{3})+", digits):
            found.add(int(re.sub(r"[ .,]", "", digits)))
        else:
            found.add(int(float(digits.replace(",", "."))))
    return found


# Words that a fact raising the level must hold in its quote.
FLAG_WORDS = {
    "sensitive_data": r"santé|médic|medical|health|patient|banc|bank|iban|carte bancaire|credit card|card number"
                      r"|identité|identity|passeport|passport|sécurité sociale|social security|fiscal|tax",
    "vital_services": r"hôpita|hospital|clinique|clinic|énergie|energy|électri|electric|gaz|gas|eau potable|water"
                      r"|transport|train|métro|metro|aéroport|airport|santé|health",
    "public_service_down": r"mairie|commune|collectivité|ville|département|région|préfecture|ministère|administration"
                           r"|service public|town|city|municipal|county|council|government|agency|public service",
    "supplier_attack": r"fournisseur|prestataire|sous-traitant|supply chain|supplier|vendor|provider|chaîne d'approvisionnement",
    "national_impact": r"national|tout le pays|nationwide|country-wide|whole country|à l'échelle du pays",
}


@dataclass
class Verified:
    """The facts of an article that the code keeps: each one proven by a quote of the article."""

    kind: str
    victim: str
    sector: str | None = None
    attacker: str | None = None
    claimed_by: str | None = None
    confirmed_by: str | None = None
    country: str | None = None
    authority: str | None = None
    people: int | None = None
    sensitive: bool = False
    data_types: list[str] = field(default_factory=list)
    outage_days: int | None = None
    vital: bool = False
    public_service_down: bool = False
    supplier: bool = False
    national: bool = False
    cves: list[str] = field(default_factory=list)
    attack_date: str | None = None
    actions: list[str] = field(default_factory=list)
    dropped: int = 0  # facts given by the AI and not kept

    def for_writing(self) -> dict:
        """What the second call to the AI receives: the facts kept, never the article."""
        return {
            "type": self.kind, "victime": self.victim, "secteur": self.sector, "attaquant": self.attacker,
            "revendique_par": self.claimed_by, "confirme_par": self.confirmed_by, "pays_attribue": self.country,
            "attribue_par": self.authority, "personnes_touchees": self.people, "donnees_sensibles": self.sensitive,
            "types_de_donnees": self.data_types, "duree_panne_jours": self.outage_days, "services_vitaux": self.vital,
            "service_public_paralyse": self.public_service_down, "fournisseur_pirate": self.supplier,
            "impact_national": self.national, "cve": self.cves, "date_attaque": self.attack_date,
            "actions_recommandees": self.actions,
        }

    def numbers(self) -> set[int]:
        """The numbers a text written from these facts may hold."""
        found = {n for n in (self.people, self.outage_days) if n is not None}
        for cve in self.cves:
            found |= {int(part) for part in cve.split("-")[1:]}
        if self.attack_date:
            found |= {int(part) for part in self.attack_date.split("-")}
        for value in (self.victim, self.attacker, self.claimed_by, *self.data_types, *self.actions):
            found |= numbers_in(value or "")
        return found


def verify(facts: Facts, article: str) -> Verified | None:
    """The facts proven by the article, or None when it reports no incident, or names no victim
    that its quote proves."""
    text = normal(article)
    dropped = 0

    def keep(item: Quoted, *, value_in_quote: bool = True) -> str | None:
        nonlocal dropped
        if item.value is None:
            return None
        if quoted(item.quote, text) and (not value_in_quote or said_in(item.value, item.quote)):
            return " ".join(item.value.split())
        dropped += 1
        return None

    def flag(name: str) -> bool:
        nonlocal dropped
        item: QuotedFlag = getattr(facts, name)
        if not item.value:
            return False
        # Both sides without accents nor capitals: "santé" in the table matches "Santé" or "sante".
        if quoted(item.quote, text) and re.search(fold(FLAG_WORDS[name]), fold(item.quote)):
            return True
        dropped += 1
        return False

    def number(item: QuotedNumber) -> int | None:
        nonlocal dropped
        if item.value is None:
            return None
        if quoted(item.quote, text) and item.value in numbers_in(item.quote):
            return item.value
        dropped += 1
        return None

    if not facts.is_incident:
        return None
    victim = keep(facts.victim)
    if not victim:
        return None
    verified = Verified(kind=facts.type, victim=victim)
    verified.sector = keep(facts.sector, value_in_quote=False)
    verified.attacker = keep(facts.attacker)
    verified.claimed_by = keep(facts.claimed_by)
    verified.confirmed_by = keep(facts.confirmed_by, value_in_quote=False)
    attribution = facts.attribution
    if attribution.country:
        quote = attribution.quote or ""
        authority = next((name for name in config.AUTHORITIES if re.search(rf"(?<!\w){re.escape(fold(name))}(?!\w)", fold(quote))), None)
        if quoted(quote, text) and said_in(attribution.country, quote) and authority:
            verified.country, verified.authority = " ".join(attribution.country.split()), authority
        else:
            dropped += 1
    verified.people = number(facts.people_affected)
    verified.outage_days = number(facts.outage_days)
    verified.sensitive = flag("sensitive_data")
    verified.vital = flag("vital_services")
    verified.public_service_down = flag("public_service_down")
    verified.supplier = flag("supplier_attack")
    verified.national = flag("national_impact")
    verified.data_types = [value for item in facts.data_types if (value := keep(item, value_in_quote=False))]
    verified.cves = [value for item in facts.cves if (value := keep(item)) and CVE.fullmatch(value)]
    attack_date = keep(facts.attack_date, value_in_quote=False)
    try:
        verified.attack_date = date.fromisoformat(attack_date).isoformat() if attack_date else None
    except ValueError:
        dropped += 1
    verified.actions = [value for item in facts.recommended_actions if (value := keep(item, value_in_quote=False))]
    verified.dropped = dropped
    return verified


# Level, decided by the code from the facts kept (B8) --------------------------------------------


def level(facts: Verified) -> tuple[str, dict]:
    """The highest level a criterion of the grid reaches, and the reason, in French and English."""
    people = facts.people or 0
    rules = (
        (people >= 1_000_000 and facts.sensitive, "critique",
         "Données sensibles d'au moins 1 000 000 de personnes.", "Sensitive data of at least 1,000,000 people."),
        (facts.vital, "critique", "Services vitaux touchés.", "Vital services hit."),
        (facts.national, "critique", "Impact national.", "Nationwide impact."),
        (facts.supplier, "critique", "Fournisseur piraté pour attaquer ses clients.", "Supplier hacked to attack its customers."),
        (people > 100_000, "grave", "Plus de 100 000 personnes touchées.", "More than 100,000 people affected."),
        (facts.sensitive, "grave", "Données sensibles volées.", "Sensitive data stolen."),
        ((facts.outage_days or 0) > 7, "grave", "Panne de plus de 7 jours.", "Outage of more than 7 days."),
        (facts.public_service_down, "grave", "Service public paralysé.", "Public service paralysed."),
        (people >= 1_000, "significative", "De 1 000 à 100 000 personnes touchées.", "1,000 to 100,000 people affected."),
        ((facts.outage_days or 0) > 0, "significative", "Organisation paralysée moins de 7 jours.",
         "Organisation paralysed for less than 7 days."),
    )
    for reached, name, fr, en in rules:
        if reached:
            return name, {"fr": fr, "en": en}
    return "mineure", {"fr": "Aucun critère plus élevé n'est établi par l'article.",
                       "en": "No higher criterion is established by the article."}
