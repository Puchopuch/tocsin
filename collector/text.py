"""French text helpers shared by the cards and the severity rules."""

import re
import unicodedata
from datetime import date

MONTHS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


def fold(text: str) -> str:
    """Lower case without accents, to compare names."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def words(text: str) -> int:
    return len(text.split())


def de(name: str) -> str:
    """French elision: "de Synology", but "d'Apple"."""
    return f"d'{name}" if name[:1] and fold(name[:1]) in "aeiouy" else f"de {name}"


def french_date(day: date) -> str:
    """"18 novembre 2026", "1er décembre 2026"."""
    return f"{'1er' if day.day == 1 else day.day} {MONTHS[day.month - 1]} {day.year}"


def mentions(text: str, name: str) -> bool:
    """True when the text names it as a whole word, whatever the accents and the case."""
    pattern = rf"(?<![\w-]){re.escape(fold(name))}(?![\w-])"
    return re.search(pattern, fold(text)) is not None
