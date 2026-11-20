"""Cards built without AI (phase 1, B6). Each card is made of fixed sentences filled with fields of
its source; when a sentence is longer than the limits of B5, its generic variant is used. What the
source does not say stays empty, and the site shows "Non communiqué"."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from datetime import date, datetime, timezone

from . import config, severity
from .models import CertfrAlert, Claim, KevEntry
from .text import de, fold, french_date, mentions, words

CISA_CATALOG = "https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search_api_fulltext={}"
NVD = "https://nvd.nist.gov/vuln/detail/{}"
GENERIC_PRODUCTS = frozenset({"multiple products", "multiple", "products"})
NAME_TOKEN = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*\.?")
SHORT_NAME = re.compile(r"^(?P<long>.+?)\s*\((?P<short>[^()\s]{2,20})\)\s*$")


def moment(value: date | datetime) -> str:
    """The day alone when the source gives no time (or only midnight), else a UTC time with Z."""
    if not isinstance(value, datetime):
        return value.isoformat()
    value = value.astimezone(timezone.utc)
    if (value.hour, value.minute, value.second, value.microsecond) == (0, 0, 0, 0):
        return value.date().isoformat()
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def day_of(value: date | datetime) -> date:
    return value.astimezone(timezone.utc).date() if isinstance(value, datetime) else value


def fitting(candidates: list[str | None], limit: int, measure: Callable[[str], int] = len) -> str:
    """The first sentence within the limit. The last candidate is the generic variant."""
    options = [candidate for candidate in candidates if candidate]
    return next((option for option in options if measure(option) <= limit), options[-1])


def is_consumer(vendor: str, texts: list[str]) -> bool:
    """True when the source names a consumer product: a browser, a system, a common app, or
    equipment found at home (network storage, box, router, media server)."""
    text = " ".join(texts)
    if any(mentions(text, phrase) for phrase in config.NOT_CONSUMER):
        return False
    return any(
        (product is None or mentions(text, product))
        and (owner is None or mentions(vendor, owner) or mentions(text, owner))
        for owner, product in config.CONSUMER_PRODUCTS
    )


def capitals(text: str) -> str:
    return "".join(char for char in text if char.isupper())


def short_name(vendor: str, product: str) -> str | None:
    """The short name a product gives in brackets, when it is its abbreviation: "DSM" for
    "DiskStation Manager (DSM)", "REDCap" for "Research Electronic Data Capture (REDCap)". Brackets
    that only qualify the product, such as "(Chromium-based)", do not count."""
    match = SHORT_NAME.match(product)
    if not match:
        return None
    letters = capitals(match["short"])
    if len(letters) < 2:
        return None
    if letters in (capitals(match["long"]), capitals(f"{vendor} {match['long']}")):
        return match["short"]
    return None


def full_name(vendor: str, product: str) -> str | None:
    """Vendor and product as the source gives them, without repeating the vendor. None for
    "Multiple Products"."""
    if fold(product) in GENERIC_PRODUCTS:
        return None
    return product if fold(vendor) in fold(product) else f"{vendor} {product}"


def product_name(vendor: str, product: str) -> str | None:
    """How a card names the product: its short name when it has one, after the vendor when the
    vendor is a single word ("Synology DSM", but "REDCap"); otherwise the full name."""
    short = short_name(vendor, product)
    if short and fold(product) not in GENERIC_PRODUCTS:
        if len(vendor.split()) == 1 and fold(vendor) not in fold(short):
            return f"{vendor} {short}"
        return short
    return full_name(vendor, product)


def unknown_attacker() -> dict:
    return {"name": None, "country": None, "status": "inconnu", "source": None}


# CISA (KEV)


def kev_card(entry: KevEntry) -> dict:
    vendor, product, cve = entry.vendor, entry.product, entry.cve
    generic = fold(product) in GENERIC_PRODUCTS
    named = product_name(vendor, product)  # in the title and the short sentences
    full = full_name(vendor, product)  # in the summary, as the source gives it
    widespread = severity.is_widespread(vendor, product)
    level, reason = severity.KEV_WIDESPREAD if widespread else severity.KEV_NICHE
    title = fitting([
        f"Faille exploitée dans {named}" if named else f"Faille exploitée dans des produits {vendor}",
        f"Faille exploitée dans un logiciel {de(vendor)}",
        "Faille exploitée dans un logiciel",
    ], config.MAX_TITLE_WORDS, words)
    victim = fitting([
        f"Utilisateurs {de(named)}" if named else f"Utilisateurs de produits {vendor}",
        None if generic else f"Utilisateurs {de(product)}",
        "Utilisateurs de ce logiciel",
    ], config.MAX_SHORT)
    affected = fitting([
        f"Oui, si vous utilisez {named} sans la dernière mise à jour." if named
        else f"Oui, si vous utilisez un produit {vendor} sans la dernière mise à jour.",
        None if generic else f"Oui, si vous utilisez {product} sans la dernière mise à jour.",
        "Oui, si vous utilisez ce logiciel sans la dernière mise à jour.",
    ], config.MAX_LINE)
    action = fitting([
        f"Installez la mise à jour de sécurité {de(vendor)} sans attendre.",
        "Installez la dernière mise à jour de sécurité sans attendre.",
    ], config.MAX_LINE)
    flaw = f"cette faille {de(full)}" if full else f"cette faille de produits {vendor}"
    summary = (
        f"La CISA, l'agence américaine de cybersécurité, a ajouté {flaw} "
        f"à sa liste des failles exploitées le {french_date(entry.date_added)}."
    )
    if fold(entry.ransomware) == "known":
        summary += " Elle sert déjà dans des attaques par rançongiciel, selon la CISA."
    timeline = [{"date": entry.date_added.isoformat(), "label": "Ajout à la liste des failles exploitées de la CISA"}]
    if entry.due_date:
        timeline.append({
            "date": entry.due_date.isoformat(),
            "label": "Date limite de correction pour les administrations américaines",
        })
    # The product named by the source; its description too when it only says "Multiple Products".
    named_texts = [product, entry.name] + ([entry.description] if generic else [])
    return {
        "id": f"kev-{cve}",
        "severity": level,
        "severity_reason": reason,
        "title": title,
        "first_seen": entry.date_added.isoformat(),
        "audience": "les_deux" if is_consumer(vendor, named_texts) else "entreprises",
        "reliability": "confirme",
        "reliability_source": None,
        # The CISA lists only flaws already exploited: this source confirms it.
        "exploited": True,
        "attacker": unknown_attacker(),
        "victim": {"label": victim, "status": "confirme"},
        "method": "Faille déjà exploitée par des attaquants",
        "loot": "Accès possible aux systèmes non mis à jour",
        "am_i_affected": affected,
        "action": action,
        "summary": [summary],
        "timeline": timeline,
        "protection_steps": [],
        "technical": {"cves": [cve], "software": [full or vendor], "techniques": []},
        "sources": [
            {
                "name": "CISA",
                "title": f"Catalogue des failles exploitées : {cve}",
                "url": CISA_CATALOG.format(cve),
                "official": True,
            },
            {"name": "NVD", "title": f"Fiche {cve}", "url": NVD.format(cve), "official": True},
        ],
    }


# CERT-FR


def clean_alert_title(title: str) -> str:
    """The alert title without "[MàJ]" at the start and without the date in brackets at the end."""
    title = re.sub(r"^\s*\[\s*m[aà]j\s*\]\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*\(\s*\d{1,2}(?:er)?\s+[^\W\d_]+\s+\d{4}\s*\)\s*$", "", title)
    return " ".join(title.split())


def certfr_source(alert: CertfrAlert) -> dict:
    return {"name": "CERT-FR", "title": f"Alerte {alert.number}", "url": alert.url, "official": True}


def certfr_card(alert: CertfrAlert) -> dict | None:
    """A card for an alert that cites no flaw already on a CISA card. None when its title is longer
    than 10 words: that alert waits for phase 2 (B6). An alert may report a flaw that nobody has
    exploited yet, so this card never says "exploitée"."""
    title = clean_alert_title(alert.title)
    if words(title) > config.MAX_TITLE_WORDS:
        return None
    level, reason = severity.CERTFR_ALERT
    published = moment(alert.published)
    return {
        "id": f"certfr-{alert.number.removeprefix('CERTFR-')}",
        "severity": level,
        "severity_reason": reason,
        "title": title,
        "first_seen": published,
        "audience": "les_deux" if is_consumer("", [title]) else "entreprises",
        "reliability": "confirme",
        "reliability_source": None,
        "exploited": False,
        "attacker": unknown_attacker(),
        "victim": {"label": "Utilisateurs des produits cités", "status": "confirme"},
        "method": "Faille signalée par le CERT-FR" if alert.cves else None,
        "loot": None,
        "am_i_affected": "Oui, si vous utilisez un produit cité dans l'alerte.",
        "action": "Suivez les recommandations de l'alerte du CERT-FR.",
        "summary": [
            f"Le CERT-FR a publié le {french_date(day_of(alert.published))} "
            f"l'alerte {alert.number} : {title}."
        ],
        "timeline": [{"date": published, "label": f"Alerte {alert.number} du CERT-FR"}],
        "protection_steps": [],
        "technical": {"cves": list(alert.cves), "software": [], "techniques": []},
        "sources": [certfr_source(alert)],
    }


def add_alert(card: dict, alert: CertfrAlert) -> None:
    """B6: an alert citing a flaw already on a CISA card becomes an official source of that card,
    with its date in the timeline. The card takes the higher of the two levels (B8)."""
    card["sources"].append(certfr_source(alert))
    card["timeline"].append({"date": moment(alert.published), "label": f"Alerte {alert.number} du CERT-FR"})
    card["timeline"].sort(key=lambda event: event["date"])
    level, reason = severity.CERTFR_ALERT
    if severity.rank(level) < severity.rank(card["severity"]):
        card["severity"], card["severity_reason"] = level, reason


# ransomware.live


def looks_like_person(name: str) -> bool:
    """True when a victim name may be a person's (B5 rule 7). Without AI the code cannot be sure, so
    a title such as "Dr" or "Maître", or a common first name followed by one or two words, is
    enough to hold the claim back. A number, a domain or a word such as "SAS" or "Mairie" points
    to an organisation."""
    tokens = [fold(token).rstrip(".") for token in NAME_TOKEN.findall(name)]
    if not tokens:
        return False
    if any(token in config.PERSON_TITLES for token in tokens):
        return True
    if re.search(r"\d|@|/|\.[a-z]{2,}\b", fold(name)):
        return False
    if any(token in config.ORGANISATION_WORDS for token in tokens):
        return False
    first = re.split(r"['’-]", tokens[0])[0]
    return 2 <= len(tokens) <= 3 and first in config.FIRST_NAMES


def claim_card(claim: Claim) -> dict:
    group = claim.group[:1].upper() + claim.group[1:]
    victim = claim.victim
    day = day_of(claim.discovered)
    level, reason = severity.CLAIM
    digest = hashlib.sha256(f"{fold(claim.group)}|{fold(victim)}|{day}".encode()).hexdigest()[:12]
    return {
        "id": f"rl-{digest}",
        "severity": level,
        "severity_reason": reason,
        "title": fitting([
            f"Attaque revendiquée contre {victim}",
            f"Attaque revendiquée par le groupe {group}",
            "Attaque revendiquée par un groupe de rançongiciel",
        ], config.MAX_TITLE_WORDS, words),
        "first_seen": moment(claim.discovered),
        "audience": "entreprises",
        # The claim itself is certain: ransomware.live recorded it. The attack is not, hence the
        # "revendique" statuses, which the site shows as "Revendiqué, non confirmé".
        "reliability": "confirme",
        "reliability_source": None,
        "exploited": False,
        "attacker": {"name": f"Groupe {group}", "country": None, "status": "revendique", "source": None},
        "victim": {"label": victim, "status": "revendique"},
        "method": "Inconnue à ce stade",
        "loot": "Données volées, selon les pirates",
        "am_i_affected": "Peut-être, si vous êtes client ou salarié de cette organisation.",
        "action": "Méfiez-vous des messages qui citent cette organisation.",
        "summary": [
            f"Le groupe {group} affirme avoir attaqué {victim}. La revendication a été relevée par "
            f"ransomware.live le {french_date(day)}. Elle n'est pas confirmée à ce stade."
        ],
        "timeline": [{"date": moment(claim.discovered), "label": "Revendication relevée par ransomware.live"}],
        "protection_steps": [],
        "technical": {"cves": [], "software": [], "techniques": []},
        "sources": [{
            "name": "ransomware.live",
            "title": f"Revendication du groupe {group}",
            "url": claim.permalink,
            "official": False,
        }],
    }


def build(
    kev_entries: list[KevEntry], alerts: list[CertfrAlert], claims: list[Claim]
) -> tuple[list[dict], list[tuple[str, str]]]:
    """The cards of phase 1, and what was held back as (reason, detail). Details may hold names:
    they go to the local journal only."""
    cards = [kev_card(entry) for entry in kev_entries]
    by_cve = {card["technical"]["cves"][0]: card for card in cards}
    held: list[tuple[str, str]] = []
    for alert in alerts:
        matches = [by_cve[cve] for cve in alert.cves if cve in by_cve]
        for card in matches:
            add_alert(card, alert)
        if matches:
            continue
        card = certfr_card(alert)
        if card is None:
            held.append(("titre d'alerte de plus de 10 mots, en attente de la phase 2", alert.number))
        else:
            cards.append(card)
    for claim in claims:
        if looks_like_person(claim.victim):
            held.append(("nom qui ressemble à celui d'une personne", f"{claim.group} / {claim.victim}"))
        else:
            cards.append(claim_card(claim))
    unique = {}
    for card in cards:
        unique.setdefault(card["id"], card)
    return [severity.cap_claim(card) for card in unique.values()], held
