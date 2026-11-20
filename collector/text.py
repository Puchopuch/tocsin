"""Text helpers shared by the sources, the cards and the severity rules, in French and in English."""

import re
import unicodedata
from datetime import date

# Unicode categories taken out of the texts of the sources: format characters (zero-width spaces,
# bidi controls such as U+202E and U+2066 to U+2069, soft hyphen, byte order mark, tag
# characters), private use and unassigned code points. Control characters and line or paragraph
# separators become spaces.
REMOVED = frozenset({"Cf", "Co", "Cn"})
SPACES = frozenset({"Cc", "Zl", "Zp"})
HIDDEN = REMOVED | SPACES | {"Cs"}


class BrokenText(ValueError):
    """A text that a sound source cannot give: not a text, a NUL byte, half of a surrogate pair,
    or far too long. Its entry is skipped."""


def clean(value: object, limit: int) -> str:
    """A text read from a source, ready for a card: control, invisible and bidi characters taken
    out, spaces collapsed, Unicode in NFC. None gives "". Raises BrokenText (see above)."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise BrokenText("pas un texte")
    if len(value) > limit:
        raise BrokenText(f"texte de plus de {limit} caractères")
    if "\x00" in value:
        raise BrokenText("octet nul")
    if any("\ud800" <= char <= "\udfff" for char in value):
        raise BrokenText("Unicode invalide")
    kept = []
    for char in value:
        category = unicodedata.category(char)
        if category in SPACES or char.isspace():
            kept.append(" ")
        elif category not in REMOVED:
            kept.append(char)
    return " ".join(unicodedata.normalize("NFC", "".join(kept)).split())


def is_plain(text: str) -> bool:
    """True when the text holds no character that clean() takes out, and is in NFC."""
    return not any(unicodedata.category(char) in HIDDEN for char in text) and unicodedata.normalize("NFC", text) == text

MONTHS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)
EN_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
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


def article(name: str) -> str:
    """English article: "a Synology product", but "an Apple product"."""
    return "an" if name[:1].lower() in tuple("aeiou") else "a"


def french_date(day: date) -> str:
    """"18 novembre 2026", "1er décembre 2026"."""
    return f"{'1er' if day.day == 1 else day.day} {MONTHS[day.month - 1]} {day.year}"


def english_date(day: date) -> str:
    """"18 November 2026", as the English version of the site writes dates."""
    return f"{day.day} {EN_MONTHS[day.month - 1]} {day.year}"


def mentions(text: str, name: str) -> bool:
    """True when the text names it as a whole word, whatever the accents and the case."""
    pattern = rf"(?<![\w-]){re.escape(fold(name))}(?![\w-])"
    return re.search(pattern, fold(text)) is not None
