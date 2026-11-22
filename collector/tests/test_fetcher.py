"""Politeness (B4) and secrecy of the key (B5 rule 8) in the HTTP layer."""

import httpx
import pytest

from collector import config
from collector.sources import Fetcher, SourceError
from collector.store import Store

from .helpers import FAKE_KEY, fake_key, reply

CISA = "https://www.cisa.gov/feeds/kev.json"
API = "https://api-pro.ransomware.live/victims/"


class Clock:
    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def answer(status: int = 200, body: bytes = b"ok", headers: dict | None = None):
    return httpx.MockTransport(lambda request: reply(status, body, headers))


def test_requests_name_the_project():
    seen = []
    transport = httpx.MockTransport(lambda request: seen.append(request) or reply(200))
    with Fetcher(transport=transport, sleep=lambda seconds: None) as fetcher:
        fetcher.get(CISA)
    assert seen[0].headers["User-Agent"] == config.USER_AGENT


def test_one_request_per_second_per_site(monkeypatch):
    monkeypatch.setattr(config, "SECONDS_BETWEEN_REQUESTS", 1.0)
    clock = Clock()
    with Fetcher(transport=answer(), clock=clock.time, sleep=clock.sleep) as fetcher:
        fetcher.get("https://www.cisa.gov/a")
        fetcher.get("https://www.cisa.gov/b")
        fetcher.get("https://cert.cyber.gouv.fr/c")
    assert clock.slept == [pytest.approx(1.0)]


def test_an_unchanged_file_is_not_downloaded_again():
    seen = []

    def server(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.headers.get("If-None-Match") == '"v1"':
            return reply(304)
        headers = {"ETag": '"v1"', "Last-Modified": "Wed, 18 Nov 2026 19:17:40 GMT"}
        return reply(200, b"catalogue", headers)

    with Store(":memory:") as store, Fetcher(store, transport=httpx.MockTransport(server), sleep=lambda s: None) as fetcher:
        first = fetcher.get(CISA)
        second = fetcher.get(CISA)
    assert first == second == b"catalogue"
    assert seen[1].headers["If-None-Match"] == '"v1"'
    assert seen[1].headers["If-Modified-Since"] == "Wed, 18 Nov 2026 19:17:40 GMT"


def test_http_errors_never_repeat_the_key():
    with Fetcher(transport=answer(401, b"invalid key"), sleep=lambda seconds: None) as fetcher:
        with pytest.raises(SourceError) as caught:
            fetcher.get(API, key=fake_key())
    assert caught.value.status == 401
    assert FAKE_KEY not in str(caught.value)


def test_network_errors_never_repeat_the_key():
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot reach {request.url} with {request.headers}", request=request)

    with Fetcher(transport=httpx.MockTransport(fail), sleep=lambda seconds: None) as fetcher:
        with pytest.raises(SourceError) as caught:
            fetcher.get(API, key=fake_key())
    assert FAKE_KEY not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


HINT = "vérifiez votre connexion Internet, un pare-feu ou un proxy"


@pytest.mark.parametrize("failure", [httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ReadError, httpx.ProxyError])
def test_a_source_that_does_not_answer_comes_with_a_plain_hint(failure):
    def fail(request: httpx.Request) -> httpx.Response:
        raise failure("no answer", request=request)

    with Fetcher(transport=httpx.MockTransport(fail), sleep=lambda seconds: None) as fetcher:
        with pytest.raises(SourceError) as caught:
            fetcher.get(CISA)
    assert str(caught.value) == f"www.cisa.gov : {failure.__name__} ; {HINT}"


def test_a_source_that_answers_with_an_error_gets_no_network_hint():
    with Fetcher(transport=answer(503, b"busy"), sleep=lambda seconds: None) as fetcher:
        with pytest.raises(SourceError) as caught:
            fetcher.get(CISA)
    assert str(caught.value) == "www.cisa.gov : HTTP 503"
