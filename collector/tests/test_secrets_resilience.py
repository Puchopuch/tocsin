"""Keys and resilience (A).

Keys: held as SecretStr; sent to their own API only, never through a redirect, never kept in
state.db; a fake key appears in no log, error, console, state.db or cards.json.

Resilience: a write cut in the middle leaves cards.json whole; a source that is down keeps the
previous cards and the time of the last complete collection; a deleted or damaged state.db gives
the same cards back."""

import json
import logging
from datetime import timedelta

import httpx
import pytest
from pydantic import SecretStr

from collector import config, output
from collector.models import Feed
from collector.sources import Fetcher, SourceError, ransomware_live
from collector.store import Store

from .helpers import FAKE_KEY, NOW, SOURCES, collect, fake_key, fetcher, give_key, reply, routes, written

API = "https://api-pro.ransomware.live/victims/"
LATER = NOW + timedelta(hours=2)


# Keys ------------------------------------------------------------------------------------------


def test_the_key_is_held_as_a_secret(isolated):
    give_key(isolated)
    key = ransomware_live.api_key()
    assert isinstance(key.secret, SecretStr)
    for shown in (str(key), repr(key), str(key.secret), f"{key.secret}", repr(key.secret)):
        assert FAKE_KEY not in shown


@pytest.mark.parametrize("url", [config.KEV_URL, config.CERTFR_FEED_URL, "https://www.cert.cyber.gouv.fr/robots.txt"])
def test_the_key_goes_to_its_own_api_only(url):
    seen = []
    with fetcher(SOURCES, seen) as client, pytest.raises(SourceError, match="n'est envoyée qu'à api-pro.ransomware.live"):
        client.get(url, key=fake_key())
    assert seen == []


@pytest.mark.parametrize("location", ["https://www.cisa.gov/collecte", "https://api-pro.ransomware.live/ailleurs", "/victims/2", "https://evil.example/"])
def test_the_key_never_follows_a_redirect(location):
    seen = []
    transport = httpx.MockTransport(lambda request: seen.append(request) or reply(302, headers={"Location": location}))
    with Fetcher(transport=transport, sleep=lambda seconds: None) as client:
        with pytest.raises(SourceError, match="redirection refusée"):
            client.get(API, params={"country": "FR"}, key=fake_key())
    assert len(seen) == 1 and seen[0].url.host == "api-pro.ransomware.live"


def test_a_request_with_a_key_is_never_cached(isolated):
    path = isolated / "state.db"
    answer = httpx.MockTransport(lambda request: reply(200, b"[]", {"ETag": '"v1"', "Last-Modified": "Wed, 18 Nov 2026 19:17:40 GMT"}))
    with Store(path) as store, Fetcher(store, transport=answer, sleep=lambda seconds: None) as client:
        client.get(API, key=fake_key())
        assert store.cached(API) is None
    assert FAKE_KEY.encode() not in path.read_bytes()


def test_a_fake_key_appears_nowhere(isolated, capsys, caplog):
    caplog.set_level(logging.DEBUG)
    give_key(isolated)
    echo = FAKE_KEY.encode()

    def redirect(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api-pro.ransomware.live":
            return reply(302, headers={"Location": f"https://www.cisa.gov/?k={FAKE_KEY}"})
        return routes(SOURCES).handle_request(request)

    def unreachable(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api-pro.ransomware.live":
            raise httpx.ConnectError(f"cannot reach {request.url} with {request.headers}", request=request)
        return routes(SOURCES).handle_request(request)

    collect()
    collect("check-sources")
    collect(table={**SOURCES, config.RANSOMWARE_LIVE_API: (401, b'{"error": "invalid key ' + echo + b'"}')})
    collect(table={**SOURCES, config.RANSOMWARE_LIVE_API: (200, b'{"victims": "' + echo + b'"}')})
    collect(transport=httpx.MockTransport(redirect))
    collect(transport=httpx.MockTransport(unreachable))
    printed = capsys.readouterr()
    assert "clé refusée (HTTP 401)" in printed.out and "redirection refusée" in printed.out
    for where, text in (("logs", caplog.text), ("console", printed.out + printed.err)):
        assert FAKE_KEY not in text, where
    for path in isolated.rglob("*"):
        if path.is_file() and path.name != ".env":
            assert echo not in path.read_bytes(), path.name  # state.db, journal, cards.json, temporary files


# Resilience ------------------------------------------------------------------------------------


def test_a_write_that_fails_before_the_rename_leaves_the_previous_file(isolated, monkeypatch, capsys):
    assert collect() == 0
    before = config.OUTPUT_PATH.read_bytes()

    def full_disk(*args):
        raise OSError("disque plein")

    for target in ("fsync", "replace"):
        with monkeypatch.context() as patch:
            patch.setattr(output.os, target, full_disk)
            assert collect(now=LATER) == 1
        assert config.OUTPUT_PATH.read_bytes() == before
    assert "gardé tel quel : écriture impossible (OSError)" in capsys.readouterr().out
    assert [path.name for path in config.OUTPUT_PATH.parent.iterdir()] == ["cards.json"]  # no temporary file left


def test_a_write_cut_in_the_middle_leaves_the_previous_file_whole(isolated, monkeypatch):
    assert collect() == 0
    before = config.OUTPUT_PATH.read_bytes()
    real_open = open

    class CutFile:
        """A file whose writing stops half way, as when the process is killed."""

        def __init__(self, *args, **kwargs):
            self._file = real_open(*args, **kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self._file.close()

        def write(self, text):
            self._file.write(text[: len(text) // 2])
            raise KeyboardInterrupt("coupure")

        def __getattr__(self, name):
            return getattr(self._file, name)

    monkeypatch.setattr(output, "open", CutFile, raising=False)
    with pytest.raises(KeyboardInterrupt):
        collect(now=LATER)
    assert config.OUTPUT_PATH.read_bytes() == before
    Feed.model_validate_json(before)
    assert [path.name for path in config.OUTPUT_PATH.parent.iterdir()] == ["cards.json"]


def test_a_leftover_temporary_file_changes_nothing(isolated):
    config.OUTPUT_PATH.parent.mkdir(parents=True)
    (config.OUTPUT_PATH.parent / ".cards.json.tmp").write_bytes(b'{"generated_at": "cass')
    assert collect() == 0
    Feed.model_validate(written())
    assert [path.name for path in config.OUTPUT_PATH.parent.iterdir()] == ["cards.json"]


@pytest.mark.parametrize("down", [
    {config.KEV_URL: (503, b"")},
    {config.CERTFR_FEED_URL: (500, b"")},
    {config.KEV_URL: (200, b"<html>maintenance</html>")},
    {config.RANSOMWARE_LIVE_API: (503, b"")},
], ids=["cisa-503", "certfr-500", "cisa-garbled", "ransomware-live-503"])
def test_a_source_down_keeps_the_previous_cards_and_time(isolated, capsys, down):
    give_key(isolated)
    assert collect() == 0
    before = config.OUTPUT_PATH.read_bytes()
    assert collect(table={**SOURCES, **down}, now=LATER) == 1
    assert config.OUTPUT_PATH.read_bytes() == before
    assert json.loads(before)["generated_at"] == "2026-11-20T12:00:00Z"  # "Mis à jour à" stays
    assert "gardé tel quel : une source a échoué" in capsys.readouterr().out


def test_without_a_previous_file_a_source_down_still_gives_the_other_cards(capsys):
    assert collect(table={**SOURCES, config.KEV_URL: (503, b"")}) == 1
    assert {card["id"].split("-")[0] for card in written()["attacks"]} == {"certfr"}
    assert "écrit sans la source en échec" in capsys.readouterr().out


class CachingServer:
    """The recorded sources, with an ETag: an unchanged file is answered with 304."""

    def __init__(self) -> None:
        self.full = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("If-None-Match") == '"v1"':
            return reply(304)
        for prefix, (status, body) in SOURCES.items():
            if str(request.url).startswith(prefix):
                self.full += 1
                return reply(status, body, {"ETag": '"v1"'})
        return reply(404)


def test_a_deleted_or_damaged_state_db_gives_the_same_cards_back(isolated):
    server = CachingServer()
    transport = httpx.MockTransport(server)
    assert collect(transport=transport) == 0
    first = config.OUTPUT_PATH.read_bytes()
    downloads = server.full

    assert collect(transport=transport) == 0  # from the cache: nothing downloaded again
    assert server.full == downloads and config.OUTPUT_PATH.read_bytes() == first

    config.STATE_PATH.unlink()
    assert collect(transport=transport) == 0
    assert server.full == 2 * downloads and config.OUTPUT_PATH.read_bytes() == first

    config.STATE_PATH.write_bytes(b"pas une base SQLite " * 200)
    assert collect(transport=transport) == 0
    assert config.OUTPUT_PATH.read_bytes() == first
    assert "state.db illisible : remplacé par un cache vide" in config.JOURNAL_PATH.read_text(encoding="utf-8")
