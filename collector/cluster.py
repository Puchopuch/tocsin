"""Duplicates merged (B9): one card per attack, with all its sources.

- A press card citing the CVE of a CISA or CERT-FR card joins that card as one more source.
- Press cards and claims about the same victim (name normalised: case, accents, punctuation and
  legal forms aside) within 7 days make one card. A press card receives the others: its facts are
  checked, a claim's are not, and a claim then reported by the press changes status this way.
- The merged card keeps the date of its first source, all the sources and the whole timeline.
"""

from __future__ import annotations

import re

from .output import when
from .text import fold

LEGAL_FORMS = frozenset(
    "sa sas sasu sarl eurl sci snc gie inc ltd llc plc gmbh ag bv nv spa srl sl co corp corporation company "
    "group groupe holding the le la les l".split()
)
MERGED = ("press-", "rl-")


def victim_key(card: dict) -> str | None:
    label = (card["victim"].get("label") or {}).get("fr") or ""
    words = [word for word in re.findall(r"[a-z0-9]+", fold(label)) if word not in LEGAL_FORMS]
    return " ".join(words) or None


def absorb(target: dict, other: dict) -> None:
    urls = {source["url"] for source in target["sources"]}
    target["sources"] += [source for source in other["sources"] if source["url"] not in urls]
    seen = {(event["date"], event["label"]["fr"]) for event in target["timeline"]}
    target["timeline"] += [event for event in other["timeline"] if (event["date"], event["label"]["fr"]) not in seen]
    target["timeline"].sort(key=lambda event: when(event["date"]))
    cves = target["technical"]["cves"]
    target["technical"]["cves"] = cves + [cve for cve in other["technical"]["cves"] if cve not in cves]
    if when(other["first_seen"]) < when(target["first_seen"]):
        target["first_seen"] = other["first_seen"]


def merge(cards: list[dict]) -> list[dict]:
    by_cve: dict[str, dict] = {}
    for card in cards:
        if not card["id"].startswith(MERGED):
            for cve in card["technical"]["cves"]:
                by_cve.setdefault(cve, card)
    result = [card for card in cards if not card["id"].startswith(MERGED)]
    others = sorted(
        (card for card in cards if card["id"].startswith(MERGED)),
        key=lambda card: (not card["id"].startswith("press-"), when(card["first_seen"])),
    )
    kept: list[dict] = []
    for card in others:
        target = next((by_cve[cve] for cve in card["technical"]["cves"] if cve in by_cve), None)
        key = victim_key(card)
        if target is None and key:
            target = next(
                (other for other in kept
                 if victim_key(other) == key and abs((when(other["first_seen"]) - when(card["first_seen"])).days) <= 7),
                None,
            )
        if target is None:
            kept.append(card)
            result.append(card)
        else:
            absorb(target, card)
    return result
