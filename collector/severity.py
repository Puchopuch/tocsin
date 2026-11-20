"""Severity, decided by code (B8). Phase 1 gives each kind of card the level of B6, matching a
criterion of the grid published by the site (frontend/src/lib/severity.js). The full grid, applied
to facts read by AI, comes with phase 2. The claim safety net always runs last."""

from __future__ import annotations

from . import config
from .text import fold

LEVELS = ("critique", "grave", "significative", "mineure")

# Phase 1 levels and their reasons, each one a criterion of the published grid.
KEV_WIDESPREAD = ("grave", "Faille déjà exploitée dans un logiciel répandu.")
KEV_NICHE = ("significative", "Faille déjà exploitée, dans un logiciel peu répandu.")
CERTFR_ALERT = ("grave", "Alerte du CERT-FR, qui signale un danger immédiat.")
CLAIM = ("significative", "Revendication non confirmée : niveau limité à « Significative ».")


def rank(level: str) -> int:
    """0 for the most serious level."""
    return LEVELS.index(level)


def is_widespread(vendor: str, product: str) -> bool:
    vendor = fold(vendor).strip()
    if vendor in config.WIDESPREAD_VENDORS:
        return True
    return any(name in fold(product) for name in config.WIDESPREAD_PRODUCTS.get(vendor, ()))


def cap_claim(card: dict) -> dict:
    """Safety net, applied last (B5 rule 4): a claimed or rumoured attack is never shown above
    "significative", whatever came before."""
    attacker = card.get("attacker") or {}
    unconfirmed = (
        card["victim"]["status"] == "revendique"
        or attacker.get("status") == "revendique"
        or card["reliability"] == "rumeur"
    )
    if unconfirmed and rank(card["severity"]) < rank("significative"):
        return {**card, "severity": CLAIM[0], "severity_reason": CLAIM[1]}
    return card
