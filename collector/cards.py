"""Cards built without AI (phase 1, B6), in French and in English. Each card is made of fixed
sentences filled with fields of its source. When a sentence is longer than the limits of B5 in
either language, its generic variant is used in both, so that the two languages always say the
same thing. What the source does not say stays empty, and the site shows "Non communiqué" ("Not
disclosed"). No translation service: the English sentences are written here, next to the French
ones."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from datetime import date, datetime, timezone

from . import config, flaws, severity
from .models import CertfrAlert, Claim, KevEntry
from .text import article, de, english_date, fold, french_date, mentions, words

CISA_CATALOG = "https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search_api_fulltext={}"
NVD = "https://nvd.nist.gov/vuln/detail/{}"
GENERIC_PRODUCTS = frozenset({"multiple products", "multiple", "products"})
NAME_TOKEN = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*\.?")
SHORT_NAME = re.compile(r"^(?P<long>.+?)\s*\((?P<short>[^()\s]{2,20})\)\s*$")


def text(fr: str, en: str) -> dict:
    """A text of the card, in both languages."""
    return {"fr": fr, "en": en}


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


def fitting(
    candidates: list[tuple[str, str] | None], limit: int, measure: Callable[[str], int] = len
) -> dict:
    """The first pair of sentences (French, English) within the limit in both languages. The last
    candidate is the generic variant."""
    options = [candidate for candidate in candidates if candidate]
    fr, en = next(
        (option for option in options if measure(option[0]) <= limit and measure(option[1]) <= limit),
        options[-1],
    )
    return text(fr, en)


def is_consumer(vendor: str, texts: list[str]) -> bool:
    """True when the source names a consumer product: a browser, a system, a common app, or
    equipment found at home (network storage, box, router, media server)."""
    joined = " ".join(texts)
    if any(mentions(joined, phrase) for phrase in config.NOT_CONSUMER):
        return False
    return any(
        (product is None or mentions(joined, product))
        and (owner is None or mentions(vendor, owner) or mentions(joined, owner))
        for owner, product in config.CONSUMER_PRODUCTS
    )


def capitals(value: str) -> str:
    return "".join(char for char in value if char.isupper())


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


def listed(names: list[str], and_: str) -> str:
    """"a", "a et b", "a, b et c"; beyond three names, the first three "et d'autres"."""
    if len(names) > 3:
        return f"{', '.join(names[:3])} {and_} {'d’autres' if and_ == 'et' else 'others'}".replace("’", "'")
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} {and_} {names[-1]}"


def first_up(value: str) -> str:
    return value[:1].upper() + value[1:]


def first_down(value: str) -> str:
    """Lower case for the first letter, unless the first word is an acronym (CSRF, XSS...)."""
    first = value.split(" ", 1)[0]
    return value if first.isupper() and len(first) > 1 else value[:1].lower() + value[1:]


# CISA (KEV)


def kev_card(entry: KevEntry) -> dict:
    vendor, product, cve = entry.vendor, entry.product, entry.cve
    generic = fold(product) in GENERIC_PRODUCTS
    named = product_name(vendor, product)  # in the title and the short sentences
    full = full_name(vendor, product)  # in the summary, as the source gives it
    widespread = severity.is_widespread(vendor, product)
    level, reason = severity.KEV_WIDESPREAD if widespread else severity.KEV_NICHE
    title = fitting([
        (f"Faille exploitée dans {named}", f"Exploited flaw in {named}") if named
        else (f"Faille exploitée dans des produits {vendor}", f"Exploited flaw in {vendor} products"),
        (f"Faille exploitée dans un logiciel {de(vendor)}", f"Exploited flaw in {vendor} software"),
        ("Faille exploitée dans un logiciel", "Exploited flaw in software"),
    ], config.MAX_TITLE_WORDS, words)
    victim = fitting([
        (f"Utilisateurs {de(named)}", f"{named} users") if named
        else (f"Utilisateurs de produits {vendor}", f"Users of {vendor} products"),
        None if generic else (f"Utilisateurs {de(product)}", f"{product} users"),
        ("Utilisateurs de ce logiciel", "Users of this software"),
    ], config.MAX_SHORT)
    affected = fitting([
        (f"Oui, si vous utilisez {named} sans la dernière mise à jour.",
         f"Yes, if you use {named} without the latest update.") if named
        else (f"Oui, si vous utilisez un produit {vendor} sans la dernière mise à jour.",
              f"Yes, if you use {article(vendor)} {vendor} product without the latest update."),
        None if generic else (f"Oui, si vous utilisez {product} sans la dernière mise à jour.",
                              f"Yes, if you use {product} without the latest update."),
        ("Oui, si vous utilisez ce logiciel sans la dernière mise à jour.",
         "Yes, if you use this software without the latest update."),
    ], config.MAX_LINE)
    action = fitting([
        (f"Installez la mise à jour de sécurité {de(vendor)} sans attendre.",
         f"Install the {vendor} security update without delay."),
        ("Installez la dernière mise à jour de sécurité sans attendre.",
         "Install the latest security update without delay."),
    ], config.MAX_LINE)
    # What the flaw is and what it allows, from the words of the CISA (collector/flaws.py).
    kind = flaws.flaw_type(entry.name, entry.cwes)
    result = flaws.consequence(entry.description)
    where_fr = named or f"des produits {vendor}"
    where_en = named or f"{vendor} products"
    opening_fr = f"{kind[0] if kind else 'Faille'} dans {where_fr}"
    opening_en = f"{kind[1] if kind else 'Flaw'} in {where_en}"
    if result:
        opening_fr += f" : {result.who[0]} peut {result.verb[0]}."
        opening_en += f": {result.who[1]} can {result.verb[1]}."
    else:
        opening_fr += "."
        opening_en += "."
    summary = text(
        f"{opening_fr} La CISA l'a ajoutée à sa liste des failles exploitées le {french_date(entry.date_added)}.",
        f"{opening_en} CISA added it to its list of exploited flaws on {english_date(entry.date_added)}.",
    )
    ransomware = fold(entry.ransomware) == "known"
    if ransomware:
        summary["fr"] += " Elle sert déjà dans des attaques par rançongiciel, selon la CISA."
        summary["en"] += " According to CISA, it is already used in ransomware attacks."
    timeline = [{
        "date": entry.date_added.isoformat(),
        "label": text("Ajout à la liste des failles exploitées de la CISA", "Added to the CISA list of exploited flaws"),
    }]
    if entry.due_date:
        timeline.append({
            "date": entry.due_date.isoformat(),
            "label": text(
                "Date limite de correction pour les administrations américaines",
                "Deadline for US federal agencies to fix it",
            ),
        })
    # The product named by the source; its description too when it only says "Multiple Products".
    named_texts = [product, entry.name] + ([entry.description] if generic else [])
    return {
        "id": f"kev-{cve}",
        "severity": level,
        "severity_reason": dict(reason),
        "title": title,
        "first_seen": entry.date_added.isoformat(),
        "audience": "les_deux" if is_consumer(vendor, named_texts) else "entreprises",
        "reliability": "confirme",
        "reliability_source": None,
        # The CISA lists only flaws already exploited: this source confirms it.
        "exploited": True,
        "kind": "faille",
        # Who uses the flaw is unknown, except that the CISA says when ransomware groups do.
        "attacker": {
            "name": text("Utilisée par des rançongiciels, selon la CISA", "Used by ransomware, according to CISA"),
            "country": None,
            "status": "confirme",
            "source": "CISA",
        } if ransomware else unknown_attacker(),
        "victim": {"label": victim, "status": "confirme"},
        "method": text(*kind) if kind else text("Faille déjà exploitée par des attaquants", "Flaw already exploited by attackers"),
        "loot": text(*result.label) if result else None,
        "am_i_affected": affected,
        "action": action,
        "summary": [summary],
        "timeline": timeline,
        "protection_steps": [],
        "technical": {"cves": [cve], "software": [full or vendor], "techniques": []},
        "sources": [
            {
                "name": "CISA",
                "title": text(f"Catalogue des failles exploitées : {cve}", f"Known Exploited Vulnerabilities catalog: {cve}"),
                "url": CISA_CATALOG.format(cve),
                "official": True,
            },
            {"name": "NVD", "title": text(f"Fiche {cve}", f"{cve} record"), "url": NVD.format(cve), "official": True},
        ],
    }


# CERT-FR

# The usual forms of a CERT-FR alert title, and their English. Anything else is kept as it is.
ALERT_TITLE = re.compile(
    r"(?P<kind>.+?) (?P<link>dans les produits|affectant les produits|dans|affectant|sur) (?P<what>.+)",
    re.IGNORECASE,
)
ALERT_KINDS = {
    "multiples vulnerabilites": "Multiple vulnerabilities",
    "vulnerabilite critique": "Critical vulnerability",
    "vulnerabilites": "Vulnerabilities",
    "vulnerabilite": "Vulnerability",
}
ALERT_LINKS = {
    "dans les produits": "in {what} products",
    "affectant les produits": "affecting {what} products",
    "dans": "in {what}",
    "affectant": "affecting {what}",
    "sur": "in {what}",
}
# French words that, in a product name, mean the name is a French phrase: not translated.
FRENCH_WORDS = frozenset("""
    le la les l des du de d et ou sur pour dans avec sans par chez en au aux un une ces son sa ses
    produit produits equipement equipements noyau interface interfaces administration serveur
    serveurs logiciel logiciels routeur routeurs plusieurs multiples ciblant affectant incident
    incidents securite campagne compromission exploitation exploitations attaque attaques
    controleurs installations systemes reseaux messagerie
""".split())


def translate_alert_title(title: str) -> str | None:
    """The English title of a CERT-FR alert, for its usual forms only ("Vulnérabilité dans X",
    "Multiples vulnérabilités dans X"...). None when the title says anything else, or when the
    product name holds French words: translating it would mean inventing."""
    match = ALERT_TITLE.fullmatch(title)
    if not match:
        return None
    kind = ALERT_KINDS.get(fold(match["kind"]))
    what = match["what"]
    if kind is None or any(fold(word) in FRENCH_WORDS for word in re.findall(r"[^\W\d_]+", what)):
        return None
    return f"{kind} {ALERT_LINKS[fold(match['link'])].format(what=what)}"


def clean_alert_title(title: str) -> str:
    """The alert title without "[MàJ]" at the start and without the date in brackets at the end."""
    title = re.sub(r"^\s*\[\s*m[aà]j\s*\]\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*\(\s*\d{1,2}(?:er)?\s+[^\W\d_]+\s+\d{4}\s*\)\s*$", "", title)
    return " ".join(title.split())


def certfr_source(alert: CertfrAlert) -> dict:
    return {
        "name": "CERT-FR",
        "title": text(f"Alerte {alert.number}", f"Alert {alert.number}"),
        "url": alert.url,
        "official": True,
    }


def certfr_card(alert: CertfrAlert) -> dict | None:
    """A card for an alert that cites no flaw already on a CISA card. None when its title is longer
    than 10 words: that alert waits for phase 2 (B6). An alert may report a flaw that nobody has
    exploited yet, so this card never says "exploitée"."""
    title_fr = clean_alert_title(alert.title)
    if words(title_fr) > config.MAX_TITLE_WORDS:
        return None
    translated = translate_alert_title(title_fr)
    title_en = translated or title_fr
    level, reason = severity.CERTFR_ALERT
    published = moment(alert.published)
    day = day_of(alert.published)
    # Targets and impact come from the lists "Systèmes affectés" and "Risques" of the alert page.
    products = flaws.product_names(alert.systems)
    risks = flaws.known_risks(alert.risks)
    shared = {product.split()[0] for product in products}
    victim = fitting([
        (f"Utilisateurs {de(products[0])}", f"{products[0]} users") if len(products) == 1 else None,
        (f"Utilisateurs {de(products[0])} et {products[1]}", f"{products[0]} and {products[1]} users")
        if len(products) == 2 else None,
        (f"Utilisateurs de produits {products[0].split()[0]}", f"Users of {products[0].split()[0]} products")
        if len(products) > 1 and len(shared) == 1 else None,
        ("Utilisateurs des produits cités", "Users of the products named"),
    ], config.MAX_SHORT)
    if risks:
        what_fr = listed([first_down(fr) for fr, _ in risks], "et")
        what_en = listed([first_down(en) for _, en in risks], "and")
        if products:
            what_fr += f" dans {listed(products, 'et')}"
            what_en += f" in {listed(products, 'and')}"
    else:
        what_fr, what_en = title_fr, title_en
    return {
        "id": f"certfr-{alert.number.removeprefix('CERTFR-')}",
        "severity": level,
        "severity_reason": dict(reason),
        "title": text(title_fr, title_en),
        "first_seen": published,
        "audience": "les_deux" if is_consumer("", [title_fr, *products]) else "entreprises",
        "reliability": "confirme",
        "reliability_source": None,
        "exploited": False,
        # An alert about flaws, or about a campaign of attacks when it cites no flaw.
        "kind": "faille" if alert.cves else "attaque",
        "attacker": unknown_attacker(),
        "victim": {"label": victim, "status": "confirme"},
        "method": text("Faille signalée par le CERT-FR", "Flaw reported by CERT-FR") if alert.cves else None,
        "loot": text(*risks[0]) if risks else None,
        "am_i_affected": text(
            "Oui, si vous utilisez un produit cité dans l'alerte.",
            "Yes, if you use a product named in the alert.",
        ),
        "action": text(
            "Suivez les recommandations de l'alerte du CERT-FR.",
            "Follow the recommendations of the CERT-FR alert.",
        ),
        "summary": [text(
            f"Alerte du CERT-FR du {french_date(day)} : {what_fr}.",
            f"CERT-FR alert of {english_date(day)}: {what_en}.",
        )],
        "timeline": [{"date": published, "label": text(f"Alerte {alert.number} du CERT-FR", f"CERT-FR alert {alert.number}")}],
        "protection_steps": [],
        "technical": {"cves": list(alert.cves), "software": [], "techniques": []},
        "sources": [certfr_source(alert)],
        # A title in an unusual form keeps its French words in the English version, and says so.
        "untranslated": [] if translated else ["title"],
    }


def add_alert(card: dict, alert: CertfrAlert) -> None:
    """B6: an alert citing a flaw already on a CISA card becomes an official source of that card,
    with its date in the timeline. The card takes the higher of the two levels (B8)."""
    card["sources"].append(certfr_source(alert))
    card["timeline"].append({
        "date": moment(alert.published),
        "label": text(f"Alerte {alert.number} du CERT-FR", f"CERT-FR alert {alert.number}"),
    })
    card["timeline"].sort(key=lambda event: event["date"])
    level, reason = severity.CERTFR_ALERT
    if severity.rank(level) < severity.rank(card["severity"]):
        card["severity"], card["severity_reason"] = level, dict(reason)


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
        "severity_reason": dict(reason),
        "title": fitting([
            (f"Attaque revendiquée contre {victim}", f"Attack claimed against {victim}"),
            (f"Attaque revendiquée par le groupe {group}", f"Attack claimed by the {group} group"),
            ("Attaque revendiquée par un groupe de rançongiciel", "Attack claimed by a ransomware group"),
        ], config.MAX_TITLE_WORDS, words),
        "first_seen": moment(claim.discovered),
        "audience": "entreprises",
        # The claim itself is certain: ransomware.live recorded it. The attack is not, hence the
        # "revendique" statuses, which the site shows as "Revendiqué, non confirmé".
        "reliability": "confirme",
        "reliability_source": None,
        "exploited": False,
        "kind": "attaque",
        "attacker": {"name": text(f"Groupe {group}", f"{group} group"), "country": None, "status": "revendique", "source": None},
        "victim": {"label": text(victim, victim), "status": "revendique"},
        "method": text("Inconnue à ce stade", "Unknown at this stage"),
        "loot": text("Données volées, selon les pirates", "Data stolen, according to the attackers"),
        "am_i_affected": text(
            "Peut-être, si vous êtes client ou salarié de cette organisation.",
            "Maybe, if you are a customer or an employee of this organisation.",
        ),
        "action": text(
            "Méfiez-vous des messages qui citent cette organisation.",
            "Be wary of messages that mention this organisation.",
        ),
        "summary": [text(
            f"Le groupe {group} affirme avoir attaqué {victim}. La revendication a été relevée par "
            f"ransomware.live le {french_date(day)}. Elle n'est pas confirmée à ce stade.",
            f"The {group} group claims to have attacked {victim}. The claim was recorded by "
            f"ransomware.live on {english_date(day)}. It is not confirmed at this stage.",
        )],
        "timeline": [{
            "date": moment(claim.discovered),
            "label": text("Revendication relevée par ransomware.live", "Claim recorded by ransomware.live"),
        }],
        "protection_steps": [],
        "technical": {"cves": [], "software": [], "techniques": []},
        "sources": [{
            "name": "ransomware.live",
            "title": text(f"Revendication du groupe {group}", f"Claim by the {group} group"),
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
