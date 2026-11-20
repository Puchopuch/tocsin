"""The three sources of phase 1, read from the recorded samples."""

import json
from datetime import date, datetime, timezone

import pytest

from collector import config
from collector.models import Claim, host_is
from collector.sources import SourceError, certfr, kev, ransomware_live, window_start

from .helpers import FAKE_KEY, NOW, SOURCES, fetcher, sample

RECENT_KEV = {
    "CVE-2024-10441", "CVE-2026-40217", "CVE-2026-90817", "CVE-2026-90436",
    "CVE-2026-115731", "CVE-2026-114713", "CVE-2026-123039",
}


def test_the_window_counts_whole_days():
    assert window_start(NOW) == datetime(2026, 11, 13, tzinfo=timezone.utc)


def test_kev_keeps_the_entries_of_the_last_seven_days():
    entries = kev.parse(sample("kev.json"))
    recent = kev.recent(entries, NOW)
    assert len(entries) == 14
    assert {entry.cve for entry in recent} == RECENT_KEV
    assert all(entry.date_added >= date(2026, 11, 13) for entry in recent)


def test_kev_refuses_a_broken_catalogue():
    with pytest.raises(SourceError):
        kev.parse(b"<html>maintenance</html>")


def test_certfr_reads_the_feed():
    alerts = certfr.parse(sample("certfr-alertes.xml"))
    assert len(alerts) == 6
    recent = {alert.number: alert for alert in certfr.recent(alerts, NOW)}
    assert set(recent) == {"CERTFR-2026-ALE-016", "CERTFR-2026-ALE-017"}
    nginx = recent["CERTFR-2026-ALE-017"]
    assert set(nginx.cves) == {"CVE-2026-123007", "CVE-2026-123633"}
    assert nginx.published == datetime(2026, 11, 18, tzinfo=timezone.utc)
    assert nginx.url == "https://www.cert.cyber.gouv.fr/alerte/CERTFR-2026-ALE-017/"


def test_certfr_refuses_a_broken_feed():
    with pytest.raises(SourceError):
        certfr.parse(b"<rss><channel><item>")


def test_certfr_reads_the_cves_of_the_page_when_robots_txt_allows_it():
    seen = []
    with fetcher(SOURCES, seen) as client:
        alerts = certfr.with_page_cves(client, certfr.recent(certfr.parse(sample("certfr-alertes.xml")), NOW))
    nginx = next(alert for alert in alerts if alert.number == "CERTFR-2026-ALE-017")
    assert set(nginx.cves) == {"CVE-2026-123007", "CVE-2026-123633"}
    urls = [str(request.url) for request in seen]
    assert "https://www.cert.cyber.gouv.fr/robots.txt" in urls
    assert "https://www.cert.cyber.gouv.fr/alerte/CERTFR-2026-ALE-017/" in urls


def test_certfr_never_reads_a_page_that_robots_txt_forbids():
    table = {**SOURCES, "https://www.cert.cyber.gouv.fr/robots.txt": (200, b"User-agent: *\nDisallow: /alerte/\n")}
    seen = []
    with fetcher(table, seen) as client:
        alerts = certfr.with_page_cves(client, certfr.recent(certfr.parse(sample("certfr-alertes.xml")), NOW))
    assert not any("/alerte/CERTFR" in str(request.url) for request in seen)
    assert all(alert.cves for alert in alerts)  # the CVEs of the feed remain


def test_ransomware_live_keeps_only_what_a_card_shows():
    claims = ransomware_live.parse(sample("ransomware_live.json"))
    assert "Societe Sans Lien" not in [claim.victim for claim in claims]  # its link pointed to .onion
    assert set(Claim.model_fields) == {"victim", "group", "country", "discovered", "permalink"}
    kept = json.dumps([claim.model_dump(mode="json") for claim in claims])
    for dropped in (".onion", "post_url", "screenshot", "infostealer", ".example"):
        assert dropped not in kept
    assert all(host_is(claim.permalink, "ransomware.live") for claim in claims)


def test_ransomware_live_keeps_the_followed_countries_over_seven_days():
    recent = ransomware_live.recent(ransomware_live.parse(sample("ransomware_live.json")), NOW)
    assert [claim.victim for claim in recent] == [
        "Exemple Logistique SAS",
        "Mairie de Fictiville",
        "Dr Exemple Fictif",
        "Jean Fictif",
        "Groupement Interprofessionnel Des Producteurs Fictifs De La Vallee Imaginaire",
    ]


def test_ransomware_live_times_are_utc():
    claim = ransomware_live.parse(sample("ransomware_live.json"))[0]
    assert claim.discovered == datetime(2026, 11, 18, 10, 41, 27, 531000, tzinfo=timezone.utc)


def test_ransomware_live_asks_for_the_months_of_the_window():
    assert ransomware_live.months(NOW) == [(2026, 11)]
    assert ransomware_live.months(datetime(2027, 1, 3, tzinfo=timezone.utc)) == [(2026, 12), (2027, 1)]


def test_ransomware_live_sends_the_key_in_its_header_only():
    seen = []
    with fetcher(SOURCES, seen) as client:
        claims, read = ransomware_live.fetch(client, NOW, FAKE_KEY)
    request = seen[0]
    assert request.headers["X-API-KEY"] == FAKE_KEY
    assert FAKE_KEY not in str(request.url)
    assert dict(request.url.params) == {"country": "FR", "year": "2026", "month": "11"}
    assert read == 8 and len(claims) == 5


def test_the_key_is_read_from_env(isolated):
    (isolated / ".env").write_text(f"{config.RANSOMWARE_LIVE_KEY}={FAKE_KEY}\n", encoding="utf-8")
    assert ransomware_live.api_key() == FAKE_KEY


def test_an_empty_key_counts_as_missing(isolated):
    (isolated / ".env").write_text(f"{config.RANSOMWARE_LIVE_KEY}=\n", encoding="utf-8")
    assert ransomware_live.api_key() is None


def test_answers_may_be_a_list_or_an_object():
    assert ransomware_live.rows({"victims": [{"victim": "x"}]}) == [{"victim": "x"}]
    assert ransomware_live.rows([{"victim": "x"}, "junk"]) == [{"victim": "x"}]
    assert ransomware_live.rows({"error": "unauthorized"}) == []
