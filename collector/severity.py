"""Severity, decided by code (B8). Phase 1 gives each kind of card the level of B6, matching a
criterion of the grid published by the site (frontend/src/lib/severity.js). The full grid, applied
to facts read by AI, comes with phase 2. The claim safety net always runs last."""

from __future__ import annotations

from . import config
from .text import fold

LEVELS = ("critique", "grave", "significative", "mineure")

# Phase 1 levels and their reasons, in French and in English, each one a criterion of the
# published grid.
KEV_WIDESPREAD = ("grave", {
    "fr": "Faille déjà exploitée dans un logiciel répandu.",
    "en": "Flaw already exploited in widespread software.",
})
KEV_NICHE = ("significative", {
    "fr": "Faille déjà exploitée, dans un logiciel peu répandu.",
    "en": "Flaw already exploited, in less common software.",
})
CERTFR_ALERT = ("grave", {
    "fr": "Alerte du CERT-FR, qui signale un danger immédiat.",
    "en": "CERT-FR alert, which warns of an immediate danger.",
})
CLAIM = ("significative", {
    "fr": "Revendication non confirmée : niveau limité à « Significative ».",
    "en": "Unconfirmed claim: level capped at “Significant”.",
})


def rank(level: str) -> int:
    """0 for the most serious level."""
    return LEVELS.index(level)


def is_widespread(vendor: str, product: str) -> bool:
    vendor = fold(vendor).strip()
    if vendor in config.WIDESPREAD_VENDORS:
        return True
    return any(name in fold(product) for name in config.WIDESPREAD_PRODUCTS.get(vendor, ()))


def cap_claim(card: dict) -> dict:
    """Safety net, applied last (B5 rule 4): an attack that is only claimed, or a rumour, is never
    shown above "significative", whatever came before. Once the victim confirms the attack, a
    group that claims it no longer limits the level (B9): the attack is real, only its author is
    claimed."""
    unconfirmed = card["victim"]["status"] == "revendique" or card["reliability"] == "rumeur"
    if unconfirmed and rank(card["severity"]) < rank("significative"):
        return {**card, "severity": CLAIM[0], "severity_reason": dict(CLAIM[1])}
    return card
