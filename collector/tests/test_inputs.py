"""What the sources send is never trusted (A): XML read without any DTD (XXE, billion laughs),
broken JSON and HTML, huge texts, NUL bytes and invalid Unicode, invisible and bidi characters,
dangerous links, SQL in values. A broken entry is skipped, the collection goes on, and the error
is clean."""

import ast
import builtins
import json
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from collector import cards, config
from collector.models import Card, host_is, is_safe_url
from collector.sources import SourceError, certfr, kev, ransomware_live
from collector.store import Cached, Store
from collector.text import BrokenText, clean, is_plain

from .helpers import NOW, SOURCES, collect, fetcher, sample, written

CODE = Path(__file__).resolve().parent.parent


def code_files() -> list[Path]:
    return [path for path in CODE.rglob("*.py") if "tests" not in path.parts]


# XML -------------------------------------------------------------------------------------------

ITEM = (
    "<item><title>{title}</title><link>{link}</link>"
    "<pubDate>Wed, 18 Nov 2026 10:00:00 +0000</pubDate><description>CVE-2026-99999</description></item>"
)
LINK = "https://www.cert.cyber.gouv.fr/alerte/CERTFR-2026-ALE-099/"


def feed(*items: str, head: str = "") -> bytes:
    return f'<?xml version="1.0" encoding="utf-8"?>{head}<rss><channel>{"".join(items)}</channel></rss>'.encode()


XXE = feed(ITEM.format(title="&xxe;", link=LINK), head='<!DOCTYPE rss [<!ENTITY xxe SYSTEM "file:///C:/Windows/win.ini">]>')
LAUGHS = feed(
    ITEM.format(title="&lol9;", link=LINK),
    head="<!DOCTYPE rss [<!ENTITY lol0 'lol'>"
    + "".join(f"<!ENTITY lol{n} '{f'&lol{n - 1};' * 10}'>" for n in range(1, 10))
    + "]>",
)
EXTERNAL_DTD = feed(ITEM.format(title="x", link=LINK), head='<!DOCTYPE rss SYSTEM "https://evil.example/rss.dtd">')
PARAMETER_ENTITY = feed(ITEM.format(title="x", link=LINK), head='<!DOCTYPE rss [<!ENTITY % ext SYSTEM "https://evil.example/x.dtd"> %ext;]>')


@pytest.mark.parametrize("body", [XXE, LAUGHS, EXTERNAL_DTD, PARAMETER_ENTITY], ids=["xxe", "billion-laughs", "external-dtd", "parameter-entity"])
def test_the_feed_is_read_without_any_dtd(body, monkeypatch):
    opened = []
    real_open = builtins.open
    monkeypatch.setattr(builtins, "open", lambda *args, **kwargs: opened.append(args) or real_open(*args, **kwargs))
    start = time.perf_counter()
    with pytest.raises(SourceError, match="^CERT-FR : flux illisible$"):
        certfr.parse(body)
    assert time.perf_counter() - start < 1
    assert opened == []  # no file read; the network is closed to the tests anyway


def test_xml_is_read_with_defusedxml_only():
    imported = []
    for path in code_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            imported += [f"{path.name}: {name}" for name in names if name.split(".")[0] in ("xml", "lxml")]
    assert imported == []


# Broken input ----------------------------------------------------------------------------------

KEV_ROW = {"cveID": "CVE-2026-99999", "vendorProject": "Vendor", "product": "Product", "dateAdded": "2026-11-19"}


def kev_with(*rows) -> bytes:
    catalogue = json.loads(sample("kev.json"))
    catalogue["vulnerabilities"] += list(rows)
    return json.dumps(catalogue).encode()


@pytest.mark.parametrize("body", [
    b'{"vulnerabilities": [',
    b"<html>maintenance</html>",
    b"\xff\xfe\x00 pas du json",
    b"\xc3\x28 octets invalides",
    b"",
    b"null",
    b'{"vulnerabilities": "' + b"x" * 10_000_000 + b'"}',
    b"[" * 100_000 + b"]" * 100_000,
], ids=["cut", "html", "utf16-garbage", "invalid-utf8", "empty", "null", "10-mb-string", "deep-nesting"])
def test_a_broken_catalogue_is_a_clean_failure(body):
    with pytest.raises(SourceError, match="^CISA : catalogue illisible$"):
        kev.parse(body)


def test_broken_entries_are_skipped_and_the_rest_of_the_catalogue_is_kept(caplog):
    broken = [
        {**KEV_ROW, "product": "x" * 10_000_000},
        {**KEV_ROW, "vendorProject": "Ven\x00dor"},
        {**KEV_ROW, "product": "Pro\ud800duct"},
        {**KEV_ROW, "cveID": "<script>alert(1)</script>"},
        {**KEV_ROW, "vendorProject": 42},
        {**KEV_ROW, "vendorProject": "\u200b\u202e"},
        {**KEV_ROW, "dateAdded": "pas une date"},
        "pas un objet",
        None,
        [],
    ]
    entries = kev.parse(kev_with(*broken))
    assert len(entries) == 14  # the 14 sound entries of the sample
    assert "CISA : 10 entrée(s) illisible(s) ignorée(s)" in caplog.text
    assert len(caplog.text) < 1_000  # the error names a count, never the content


def test_broken_alerts_are_skipped_and_the_others_kept(caplog):
    body = feed(
        ITEM.format(title="Vulnérabilité dans Exemple", link=LINK),
        ITEM.format(title="x" * 10_000_000, link=LINK.replace("099", "098")),
        ITEM.format(title="Lien piégé", link="javascript:alert(1)"),
        ITEM.format(title="Autre site", link="https://evil.example/alerte/CERTFR-2026-ALE-097/"),
        ITEM.format(title="Lien encodé", link="https://www.cert.cyber.gouv.fr%2F@evil.example/alerte/CERTFR-2026-ALE-096/"),
    )
    alerts = certfr.parse(body)
    assert [alert.number for alert in alerts] == ["CERTFR-2026-ALE-099"]
    assert "CERT-FR : 4 alerte(s) illisible(s) ignorée(s)" in caplog.text


@pytest.mark.parametrize("body", [
    feed(ITEM.format(title="a\x00b", link=LINK)),
    feed(ITEM.format(title="x", link=LINK)).replace(b"<title>x", b"<title>\xff\xfe"),
    b"<rss>" + b"<a>" * 100_000 + b"</a>" * 100_000 + b"</rss>",
], ids=["nul-byte", "invalid-utf8", "deep-nesting"])
def test_a_broken_feed_is_a_clean_failure_or_gives_nothing(body):
    try:
        assert certfr.parse(body) == []
    except SourceError as error:
        assert str(error) == "CERT-FR : flux illisible"


@pytest.mark.parametrize("page", [
    b"\x00\xff\xfe" * 10_000,
    b"<html>" * 100_000,
    b"<a href='https://www.cve.org/CVERecord?id=" + b"9" * 10_000_000 + b"'>",
], ids=["binary", "unclosed-tags", "10-mb-link"])
def test_a_broken_alert_page_keeps_the_cves_of_the_feed(page):
    table = {**SOURCES, "https://www.cert.cyber.gouv.fr/alerte/CERTFR-2026-ALE-017/": (200, page)}
    with fetcher(table) as client:
        alerts = certfr.with_page_details(client, certfr.recent(certfr.parse(sample("certfr-alertes.xml")), NOW))
    nginx = next(alert for alert in alerts if alert.number == "CERTFR-2026-ALE-017")
    assert set(nginx.cves) == {"CVE-2026-123007", "CVE-2026-123633"}


def test_broken_claims_are_skipped():
    good = {"victim": "Exemple SAS", "group": "groupe-fictif", "country": "FR", "discovered": "2026-11-18 10:00:00",
            "permalink": "https://www.ransomware.live/id/exemple"}
    rows = [
        good,
        {**good, "victim": "x" * 10_000_000},
        {**good, "victim": "Exemple\x00SAS"},
        {**good, "group": "groupe\ud800"},
        {**good, "victim": 12345},
        {**good, "country": "France"},
        {**good, "discovered": "2026-11-18" * 1_000_000},
        {**good, "permalink": "https://evil.onion/post"},
        {**good, "permalink": None, "post_url": "https://www.ransomware.live/id/x"},
    ]
    claims = ransomware_live.parse(json.dumps(rows).encode())
    assert [claim.victim for claim in claims] == ["Exemple SAS"]
    for body in (b"[" * 100_000, b"\xff garbage", b'{"victims": ['):
        with pytest.raises(SourceError, match="^ransomware.live : réponse illisible$"):
            ransomware_live.parse(body)


def test_a_broken_source_never_stops_the_collection(capsys):
    table = {**SOURCES, config.KEV_URL: (200, b'{"vulnerabilities": [' + b'"x' * 1_000_000)}
    assert collect(table=table) == 1
    printed = capsys.readouterr()
    assert "CISA, failles exploitées : échec, CISA : catalogue illisible" in printed.out
    assert "Traceback" not in printed.out + printed.err
    assert max(len(line) for line in printed.out.splitlines()) < 300
    assert {card["id"].split("-")[0] for card in written()["attacks"]} == {"certfr"}  # the others went on


# Texts -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    ("Synology\u202eDSM", "SynologyDSM"),
    ("Apache \u2066Tomcat\u2069", "Apache Tomcat"),
    ("\u2067Cisco\u2068 IOS\u2069", "Cisco IOS"),
    ("Cisco\u200b IOS\u200d XE\u200c", "Cisco IOS XE"),
    ("\ufeffFortinet\u2060", "Fortinet"),
    ("Micro\u00adsoft", "Microsoft"),
    ("Ivanti\tConnect\nSecure\r", "Ivanti Connect Secure"),
    ("Juniper\x1b[31m Junos\x07", "Juniper [31m Junos"),
    ("Lin\u2028ux\u2029", "Lin ux"),
    ("A\u00a0B\u202fC", "A B C"),
    ("Vulne\u0301rabilite\u0301", "Vulnérabilité"),
    ("Fo\U000e0041rtinet\ue000", "Fortinet"),
])
def test_texts_lose_control_invisible_and_bidi_characters(raw, expected):
    assert clean(raw, 300) == expected
    assert is_plain(clean(raw, 300))


@pytest.mark.parametrize("raw", ["a\x00b", "a\ud800b", "x" * 301, 42, b"octets"], ids=["nul", "surrogate", "too-long", "number", "bytes"])
def test_broken_texts_are_refused(raw):
    with pytest.raises(BrokenText):
        clean(raw, 300)


def test_hidden_characters_never_reach_a_card():
    rows = [{**KEV_ROW, "vendorProject": "Syno\u200blogy", "product": "Disk\u202eStation Manager (\u2066DSM\u2069)"}]
    entries = kev.recent(kev.parse(kev_with(*rows)), NOW)
    built, _ = cards.build(entries, [], [])
    texts = json.dumps(built, ensure_ascii=False)
    assert all(is_plain(char) for char in texts)
    assert "Faille exploitée dans Synology DSM" in texts


def test_the_card_model_refuses_hidden_characters():
    card = cards.build(kev.recent(kev.parse(sample("kev.json")), NOW), [], [])[0][0]
    for hidden in ("\u202e", "\u2066", "\u200b", "\x1b", "e\u0301"):
        broken = json.loads(json.dumps(card))
        broken["title"]["en"] += hidden
        with pytest.raises(ValidationError):
            Card.model_validate(broken)


# Links -----------------------------------------------------------------------------------------

# The same cases are checked by the site (frontend/scripts/check.mjs).
LINKS = json.loads(sample("links.json"))
REFUSED_LINKS = [*LINKS["refused"], None, 42, "https://www.cert.cyber.gouv.fr/" + "a" * 2_000]
ACCEPTED_LINKS = LINKS["accepted"]


@pytest.mark.parametrize("url", REFUSED_LINKS)
def test_dangerous_links_are_refused(url):
    assert not is_safe_url(url)


@pytest.mark.parametrize("url", ACCEPTED_LINKS)
def test_plain_https_links_are_accepted(url):
    assert is_safe_url(url)


def test_a_link_must_point_to_the_domain_of_its_source():
    assert host_is("https://www.cert.cyber.gouv.fr/alerte/", "cert.cyber.gouv.fr")
    assert not host_is("https://www.cert.cyber.gouv.fr.evil.example/", "cert.cyber.gouv.fr")
    assert not host_is("https://evilcert.cyber.gouv.fr/", "cert.cyber.gouv.fr")
    card = cards.build(kev.recent(kev.parse(sample("kev.json")), NOW), [], [])[0][0]
    for name, url in (("CISA", "https://www.cert.cyber.gouv.fr/alerte/"), ("CERT-FR", "https://evil.example/"), ("Inconnu", "https://www.cisa.gov/")):
        broken = json.loads(json.dumps(card))
        broken["sources"][0].update(name=name, url=url)
        with pytest.raises(ValidationError):
            Card.model_validate(broken)


# SQLite ----------------------------------------------------------------------------------------

INJECTIONS = ["'; DROP TABLE http_cache; --", "l'alerte d'aujourd'hui", '" OR 1=1 --', "Robert'); DROP TABLE http_cache;--"]


def test_values_never_become_sql(isolated):
    with Store(isolated / "state.db") as store:
        for value in INJECTIONS:
            url = f"https://www.cisa.gov/{value}"
            store.save(url, value, value, value.encode())
            assert store.cached(url) == Cached(value, value, value.encode())
        tables = store._db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        rows = store._db.execute("SELECT count(*) FROM http_cache").fetchone()[0]
    assert sorted(tables) == [("ai_cache",), ("http_cache",)] and rows == len(INJECTIONS)


def test_every_query_is_a_fixed_text():
    """Every execute() receives a literal string: SQL is never built from values."""
    built = []
    for path in code_files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("execute", "executemany", "executescript"):
                first = node.args[0] if node.args else None
                if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                    built.append(f"{path.name}:{node.lineno}")
    assert built == []
