"""Helpers shared by the tests: a fixed "now", the recorded samples and a fake network."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import httpx
from pydantic import SecretStr

from collector import config
from collector.sources import ApiKey, Fetcher

DATA = Path(__file__).parent / "data"
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
FAKE_KEY = "cle-de-test-0123456789abcdef"  # not a real key


def sample(name: str) -> bytes:
    return (DATA / name).read_bytes()


def fake_key() -> ApiKey:
    return ApiKey(header="X-API-KEY", host="api-pro.ransomware.live", secret=SecretStr(FAKE_KEY))


def reply(status: int = 200, body: bytes | None = b"", headers: dict[str, str] | None = None) -> httpx.Response:
    """An answer as the network gives it: a stream that the collector reads piece by piece."""
    return httpx.Response(status, headers=headers, stream=httpx.ByteStream(body or b""))


def routes(table: dict[str, tuple[int, bytes]], seen: list | None = None) -> httpx.MockTransport:
    """A fake network: the first URL prefix that matches answers with its status and body."""

    def answer(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        for prefix, (status, body) in table.items():
            if str(request.url).startswith(prefix):
                return reply(status, body)
        return reply(404)

    return httpx.MockTransport(answer)


def fetcher(table: dict[str, tuple[int, bytes]], seen: list | None = None, store=None) -> Fetcher:
    return Fetcher(store, transport=routes(table, seen), sleep=lambda seconds: None)


def collect(*argv: str, table: dict | None = None, transport: httpx.BaseTransport | None = None, now: datetime = NOW) -> int:
    """A run of the command line on the fake network (the recorded sources by default)."""
    from collector.__main__ import main

    return main(list(argv) or ["run"], transport=transport or routes(table or SOURCES), now=now)


def give_key(folder: Path) -> None:
    (folder / ".env").write_text(f"{config.RANSOMWARE_LIVE_KEY}={FAKE_KEY}\n", encoding="utf-8")


def written() -> dict:
    import json

    return json.loads(config.OUTPUT_PATH.read_text(encoding="utf-8"))


# The three sources as recorded: CISA and CERT-FR are real extracts, ransomware.live is invented.
SOURCES = {
    config.KEV_URL: (200, sample("kev.json")),
    config.CERTFR_FEED_URL: (200, sample("certfr-alertes.xml")),
    "https://www.cert.cyber.gouv.fr/robots.txt": (200, b"User-agent: *\nDisallow: /pdf\nDisallow: /fiche/\n"),
    "https://www.cert.cyber.gouv.fr/alerte/CERTFR-2026-ALE-017/": (200, sample("certfr-page.html")),
    "https://www.cert.cyber.gouv.fr/alerte/": (200, b"<!doctype html><article></article>"),
    config.RANSOMWARE_LIVE_API: (200, sample("ransomware_live.json")),
}
