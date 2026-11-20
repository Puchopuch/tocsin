"""Validation of the cards (B10, B5 rules 2, 4, 5, 7), in both languages, and writing of cards.json
(B5 rule 9)."""

import json
from copy import deepcopy

import pytest

from collector import cards, config, output
from collector.models import Feed
from collector.sources import certfr, kev, ransomware_live

from .helpers import NOW, sample

BASE = cards.kev_card(next(entry for entry in kev.parse(sample("kev.json")) if entry.cve == "CVE-2026-40217"))


def both(fr: str, en: str) -> dict:
    return {"fr": fr, "en": en}


def changed(**fields) -> dict:
    card = deepcopy(BASE)
    card.update(fields)
    return card


def refused(card: dict) -> str:
    valid, rejected = output.check([card])
    assert not valid and len(rejected) == 1
    return rejected[0][1]


def test_a_template_card_is_valid():
    valid, rejected = output.check([BASE])
    assert len(valid) == 1 and not rejected


@pytest.mark.parametrize("url", [
    "javascript:alert(1)",
    "http://exemplefictifaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.onion/leak",
    "https://exemplefictif.onion./fuite",
    "ftp://example.org/file",
    "https://user:secret@localhost/",
    "/relative/link",
])
def test_links_other_than_plain_http_are_refused(url):
    card = changed(sources=[{"name": "Test", "title": None, "url": url, "official": False}])
    assert "sources.0.url" in refused(card)


def test_a_card_without_source_is_refused():
    assert "sources" in refused(changed(sources=[]))


def test_every_text_needs_both_languages():
    assert "title" in refused(changed(title={"fr": "Faille exploitée dans Exemple"}))
    assert "method" in refused(changed(method=both("Faille", "")))
    assert "summary" in refused(changed(summary=["Un texte sans sa version anglaise."]))


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_lengths_of_the_readme_in_each_language(lang):
    def one(long: str, short: str = "ok") -> dict:
        return {"fr": long, "en": short} if lang == "fr" else {"fr": short, "en": long}

    assert "title" in refused(changed(title=one("Un titre de onze mots ne peut jamais passer sur une carte", "Titre")))
    assert "method" in refused(changed(method=one("x" * 46)))
    assert "loot" in refused(changed(loot=one("x" * 46)))
    assert "victim.label" in refused(changed(victim={"label": one("x" * 46), "status": "confirme"}))
    assert "am_i_affected" in refused(changed(am_i_affected=one("x" * 76)))
    assert "action" in refused(changed(action=one("x" * 76)))


def test_a_claim_above_significant_is_refused():
    card = changed(severity="grave", victim={"label": both("Exemple", "Exemple"), "status": "revendique"})
    assert "revendication" in refused(card)


@pytest.mark.parametrize("lang", ["fr", "en"])
def test_personal_data_is_refused_in_each_language(lang):
    # An invented address, put together here so that the repository holds no e-mail address at all.
    address = "@".join(["contact", "exemple.example"])
    for sentence in (f"Écrire à {address}.", "Appeler le 01 23 45 67 89."):
        pair = {"fr": sentence, "en": "Nothing here."} if lang == "fr" else {"fr": "Rien ici.", "en": sentence}
        assert "personnelle" in refused(changed(summary=[pair]))


def test_an_attacker_country_needs_its_source():
    attacker = {"name": both("Groupe Fictif", "Fictif group"), "country": both("Fictivie", "Fictivia"), "status": "presume", "source": None}
    assert "attacker" in refused(changed(attacker=attacker))


def test_times_are_utc_or_a_day_alone():
    assert "first_seen" in refused(changed(first_seen="2026-11-18T07:42:00"))
    assert "first_seen" in refused(changed(first_seen="2026-11-18T07:42:00+01:00"))
    valid, _ = output.check([changed(first_seen="2026-11-18T07:42:00Z")])
    assert valid


def test_reasons_never_repeat_the_content():
    name = "Organisation Fictive Au Nom Bien Trop Long Pour Une Carte"
    assert name not in refused(changed(victim={"label": both(name, name), "status": "confirme"}))


def test_on_the_same_day_an_exploited_flaw_comes_first():
    alert = changed(id="certfr-2099-ALE-001", first_seen="2026-11-18", exploited=False)
    flaw = changed(id="kev-CVE-2099-0005", first_seen="2026-11-18", exploited=True)
    newer = changed(id="certfr-2099-ALE-002", first_seen="2026-11-19", exploited=False)
    data = output.feed([alert, flaw, newer], NOW)
    assert [card["id"] for card in data["attacks"]] == ["certfr-2099-ALE-002", "kev-CVE-2099-0005", "certfr-2099-ALE-001"]


def test_the_feed_keeps_seven_days_newest_first():
    old = changed(id="kev-CVE-2099-0001", first_seen="2026-11-12")
    today = changed(id="kev-CVE-2099-0002", first_seen="2026-11-20T08:00:00Z")
    data = output.feed([old, BASE, today], NOW)
    assert [card["id"] for card in data["attacks"]] == ["kev-CVE-2099-0002", "kev-CVE-2026-40217"]
    assert data["generated_at"] == "2026-11-20T12:00:00Z"


def test_publish_writes_through_a_temporary_file():
    path = config.OUTPUT_PATH
    outcome, data = output.publish(path, [BASE], NOW, sources_ok=3)
    assert outcome == "écrit"
    assert json.loads(path.read_text(encoding="utf-8")) == data
    assert [file.name for file in path.parent.iterdir()] == ["cards.json"]


def test_publish_keeps_the_old_file_when_every_source_failed():
    path = config.OUTPUT_PATH
    output.publish(path, [BASE], NOW, sources_ok=3)
    before = path.read_bytes()
    outcome, _ = output.publish(path, [], NOW, sources_ok=0)
    assert outcome.startswith("gardé") and path.read_bytes() == before


def test_publish_never_empties_a_full_file():
    path = config.OUTPUT_PATH
    output.publish(path, [BASE], NOW, sources_ok=3)
    before = path.read_bytes()
    outcome, _ = output.publish(path, [], NOW, sources_ok=2)
    assert outcome.startswith("gardé") and path.read_bytes() == before


def test_publish_dry_run_writes_nothing():
    outcome, data = output.publish(config.OUTPUT_PATH, [BASE], NOW, sources_ok=3, dry_run=True)
    assert data["attacks"] and not config.OUTPUT_PATH.exists()


def test_the_written_file_is_accepted_by_the_card_model():
    entries = kev.recent(kev.parse(sample("kev.json")), NOW)
    alerts = certfr.recent(certfr.parse(sample("certfr-alertes.xml")), NOW)
    claims = ransomware_live.recent(ransomware_live.parse(sample("ransomware_live.json")), NOW)
    built, _ = cards.build(entries, alerts, claims)
    valid, rejected = output.check(built)
    output.publish(config.OUTPUT_PATH, valid, NOW, sources_ok=3)
    feed = Feed.model_validate(json.loads(config.OUTPUT_PATH.read_text(encoding="utf-8")))
    assert len(feed.attacks) == len(valid) == 11
    assert [card_id for card_id, _ in rejected] == [
        next(card["id"] for card in built if card["victim"]["label"]["fr"].startswith("Groupement"))
    ]
