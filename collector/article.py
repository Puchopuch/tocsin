"""The visible text of a web page, and nothing else: what a reader sees is what the AI may read.

Left out: comments, every attribute (alt, title...), scripts, styles, forms, navigation, and every
element hidden from the reader (hidden, aria-hidden, display:none, visibility:hidden, zero size,
zero opacity, white or transparent text, screen-reader-only classes). Invisible characters are
taken out by text.clean. A text hidden in a page to steer the AI never reaches it this way; a
visible one does, but then the code checks every fact against a quote, and decides the level, the
links and the statuses itself.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from .text import BrokenText, clean

SKIPPED = frozenset({
    "script", "style", "noscript", "template", "svg", "math", "iframe", "object", "embed", "canvas",
    "head", "nav", "footer", "aside", "form", "button", "select", "textarea", "label", "dialog", "menu",
})
VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"})
BLOCKS = frozenset({"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "pre", "td", "th", "dd", "dt", "figcaption"})
HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*(?:hidden|collapse)|opacity\s*:\s*0(?:\.0*)?\s*(?:;|$)"
    r"|font-size\s*:\s*0|(?:width|height|max-height|max-width)\s*:\s*0(?:px)?\s*(?:;|$)"
    r"|(?<![-\w])color\s*:\s*(?:white|#fff\b|#ffffff\b|transparent|rgba\([^)]*,\s*0\s*\))"
    r"|clip\s*:\s*rect\(\s*0|text-indent\s*:\s*-\d{3,}|left\s*:\s*-\d{3,}",
    re.IGNORECASE,
)
HIDDEN_CLASS = re.compile(r"(?:^|\s)(?:sr-only|visually-hidden|screen-reader-text|hidden|d-none|invisible)(?:\s|$)", re.IGNORECASE)


def hidden(attrs: list[tuple[str, str | None]]) -> bool:
    for name, value in attrs:
        name, value = name.lower(), value or ""
        if name == "hidden" or (name == "aria-hidden" and value.lower() == "true"):
            return True
        if name == "style" and HIDDEN_STYLE.search(value):
            return True
        if name == "class" and HIDDEN_CLASS.search(value):
            return True
    return False


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []  # (tag, left out)
        self.blocks: list[tuple[bool, list[str]]] = []  # (inside <article> or <main>, pieces)
        self.current: list[str] | None = None

    def _left_out(self) -> bool:
        return any(skip for _, skip in self.stack)

    def _inside_article(self) -> bool:
        return any(tag in ("article", "main") for tag, _ in self.stack)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in VOID:
            return
        self.stack.append((tag, tag in SKIPPED or hidden(attrs)))
        if tag in BLOCKS and not self._left_out():
            self.current = []
            self.blocks.append((self._inside_article(), self.current))

    def handle_endtag(self, tag):
        tag = tag.lower()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break
        if tag in BLOCKS:
            self.current = None

    def handle_data(self, data):
        if self.current is not None and not self._left_out():
            self.current.append(data)


def visible_text(html: str, limit: int = 200_000) -> str:
    """The visible text of the page, one paragraph per line; only the article when the page marks
    it with <article> or <main>."""
    parser = VisibleText()
    try:
        parser.feed(html[: limit * 10])
        parser.close()
    except (AssertionError, ValueError, RecursionError):
        pass
    in_article = [pieces for inside, pieces in parser.blocks if inside]
    chosen = in_article or [pieces for _, pieces in parser.blocks]
    paragraphs = []
    for pieces in chosen:
        try:
            paragraph = clean("".join(pieces), limit)
        except BrokenText:
            continue
        if paragraph and (not paragraphs or paragraphs[-1] != paragraph):
            paragraphs.append(paragraph)
    return "\n".join(paragraphs)[:limit]
