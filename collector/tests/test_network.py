"""Safety of the requests (A): https only, to the listed sites only; public addresses only, checked
after DNS resolution, at each redirect, and on the connection itself; TLS always verified; 3
redirects at most; time and size limits; compression bombs."""

import gzip
import ipaddress
import re
import socket
import ssl
import tracemalloc
import zlib
from pathlib import Path

import httpcore
import httpx
import pytest

from collector import config
from collector.sources import (
    Fetcher,
    GuardedBackend,
    GuardedTransport,
    SourceError,
    is_public,
    tls_context,
)

from .helpers import reply

CISA = "https://www.cisa.gov/feeds/kev.json"
CODE = Path(__file__).resolve().parent.parent


def code_files() -> list[Path]:
    return [path for path in CODE.rglob("*.py") if "tests" not in path.parts]


def serving(answer) -> tuple[Fetcher, list[httpx.Request]]:
    """A Fetcher on a fake network that answers with answer(request, seen)."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return answer(request, seen)

    return Fetcher(transport=httpx.MockTransport(handler), sleep=lambda seconds: None), seen


# The tests themselves -------------------------------------------------------------------------


@pytest.mark.parametrize("attempt", [
    lambda: socket.getaddrinfo("www.cisa.gov", 443),
    lambda: socket.gethostbyname("www.cisa.gov"),
    lambda: socket.create_connection(("www.cisa.gov", 443)),
    lambda: httpx.get("https://www.cisa.gov/", timeout=1),
], ids=["dns", "dns-v4", "connection", "httpx"])
def test_no_test_can_wait_for_the_network_or_a_dns_server(attempt):
    """conftest.py makes every lookup and connection fail at once."""
    with pytest.raises((RuntimeError, httpx.HTTPError)):
        attempt()


# https, listed sites ----------------------------------------------------------------------------


@pytest.mark.parametrize("url", [
    "http://www.cisa.gov/feeds/kev.json",
    "https://evil.example/kev.json",
    "https://www.cisa.gov.evil.example/kev.json",
    "https://user:secret@www.cisa.gov/kev.json",
    "https://www.cisa.gov:8443/kev.json",
    "ftp://www.cisa.gov/kev.json",
    "file:///C:/Windows/win.ini",
    "https://127.0.0.1/",
    "https://169.254.169.254/latest/meta-data/",
    "https://[::1]/",
    "javascript:alert(1)",
])
def test_only_https_to_the_listed_sites(url):
    fetcher, seen = serving(lambda request, seen: reply(200, b"ok"))
    with fetcher, pytest.raises(SourceError, match="refusée|illisible"):
        fetcher.get(url)
    assert seen == []


def test_the_sources_are_on_the_list_and_in_https():
    for url in (config.KEV_URL, config.CERTFR_FEED_URL, config.RANSOMWARE_LIVE_API):
        assert url.startswith("https://") and httpx.URL(url).host in config.ALLOWED_HOSTS


@pytest.mark.parametrize("location", [
    "http://www.cisa.gov/kev.json",
    "https://evil.example/",
    "//evil.example/kev.json",
    "https://169.254.169.254/latest/meta-data/",
    "https://user:secret@www.cisa.gov/kev.json",
    "javascript:alert(1)",
    "file:///etc/passwd",
])
def test_each_redirect_is_checked_like_the_first_request(location):
    fetcher, seen = serving(lambda request, seen: reply(302, headers={"Location": location}) if len(seen) == 1 else reply(200, b"!"))
    with fetcher, pytest.raises(SourceError, match="refusée"):
        fetcher.get(CISA)
    assert [str(request.url) for request in seen] == [CISA]


def test_three_redirects_are_followed_not_four():
    fetcher, seen = serving(lambda request, seen: reply(302, headers={"Location": f"/etape{len(seen)}"}) if len(seen) <= 3 else reply(200, b"fin"))
    with fetcher:
        assert fetcher.get(CISA) == b"fin"
    assert [request.url.path for request in seen] == ["/feeds/kev.json", "/etape1", "/etape2", "/etape3"]

    fetcher, seen = serving(lambda request, seen: reply(302, headers={"Location": f"/etape{len(seen)}"}))
    with fetcher, pytest.raises(SourceError, match="plus de 3 redirections"):
        fetcher.get(CISA)
    assert len(seen) == 4


# Public addresses only --------------------------------------------------------------------------


@pytest.mark.parametrize("address", [
    "127.0.0.1", "127.8.9.10", "10.0.0.1", "172.16.0.1", "192.168.1.1", "100.64.0.1", "0.0.0.0",
    "169.254.169.254", "224.0.0.1", "255.255.255.255", "192.0.2.1",
    "::1", "::", "fe80::1", "fec0::1", "fc00::1", "fd00:ec2::254", "ff02::1", "::127.0.0.1",
    "::ffff:127.0.0.1", "::ffff:169.254.169.254", "::ffff:10.0.0.1",
    "2002:7f00:1::", "64:ff9b::a9fe:a9fe", "2001:db8::1",
])
def test_private_local_and_metadata_addresses_are_not_public(address):
    assert not is_public(ipaddress.ip_address(address))


@pytest.mark.parametrize("address", ["8.8.8.8", "1.1.1.1", "2606:4700:4700::1111", "2001:4860:4860::8888"])
def test_internet_addresses_are_public(address):
    assert is_public(ipaddress.ip_address(address))


def dns(table: dict[str, list[str]]):
    """A fake DNS: each name resolves to its addresses."""

    def resolve(host, port, type=0, **kwargs):
        if host not in table:
            raise socket.gaierror("nom inconnu")
        return [
            (socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))
            for address in table[host]
        ]

    return resolve


class FakeStream(httpcore.NetworkStream):
    """A connection that plays back a raw HTTP answer."""

    def __init__(self, answer: bytes) -> None:
        self._answer = answer
        self.server_hostname: str | None = None

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        chunk, self._answer = self._answer[:max_bytes], self._answer[max_bytes:]
        return chunk

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        pass

    def close(self) -> None:
        pass

    def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        self.server_hostname = server_hostname
        return self

    def get_extra_info(self, info):
        return None


class FakeInternet(httpcore.NetworkBackend):
    """Stands for the network: records each address connected to, and plays back its answer."""

    def __init__(self, answers: dict[str, bytes] | None = None) -> None:
        self.answers = answers or {}
        self.connected: list[str] = []
        self.streams: list[FakeStream] = []

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        self.connected.append(host)
        if host not in self.answers:
            raise httpcore.ConnectError("injoignable")
        self.streams.append(FakeStream(self.answers[host]))
        return self.streams[-1]

    def sleep(self, seconds: float) -> None:
        pass


def guarded(names: dict[str, list[str]], answers: dict[str, bytes] | None = None) -> tuple[Fetcher, FakeInternet]:
    internet = FakeInternet(answers)
    transport = GuardedTransport(GuardedBackend(resolve=dns(names), backend=internet))
    return Fetcher(transport=transport, sleep=lambda seconds: None), internet


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "::ffff:127.0.0.1", "::1", "10.1.2.3", "fd00:ec2::254"])
def test_a_site_whose_name_gives_a_private_address_is_refused_before_connecting(address):
    fetcher, internet = guarded({"www.cisa.gov": [address]})
    with fetcher, pytest.raises(SourceError, match="adresse non publique"):
        fetcher.get(CISA)
    assert internet.connected == []


def test_one_private_address_among_public_ones_is_enough_to_refuse():
    fetcher, internet = guarded({"www.cisa.gov": ["8.8.8.8", "2606:4700:4700::1111", "127.0.0.1"]})
    with fetcher, pytest.raises(SourceError, match="adresse non publique"):
        fetcher.get(CISA)
    assert internet.connected == []


def test_the_connection_goes_to_the_checked_address_and_tls_checks_the_name():
    answer = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
    fetcher, internet = guarded({"www.cisa.gov": ["8.8.8.8"]}, {"8.8.8.8": answer})
    with fetcher:
        assert fetcher.get(CISA) == b"ok"
    assert internet.connected == ["8.8.8.8"]  # the address that was checked, not the name again
    assert internet.streams[0].server_hostname == "www.cisa.gov"


def test_each_redirect_is_resolved_and_checked_again():
    redirect = b"HTTP/1.1 302 Found\r\nLocation: https://cert.cyber.gouv.fr/alerte/feed/\r\nContent-Length: 0\r\n\r\n"
    names = {"www.cisa.gov": ["8.8.8.8"], "cert.cyber.gouv.fr": ["169.254.169.254"]}
    fetcher, internet = guarded(names, {"8.8.8.8": redirect, "169.254.169.254": b"HTTP/1.1 200 OK\r\n\r\n"})
    with fetcher, pytest.raises(SourceError, match="adresse non publique"):
        fetcher.get(CISA)
    assert internet.connected == ["8.8.8.8"]


def test_the_default_transport_is_the_guarded_one():
    with Fetcher() as fetcher:
        transport = fetcher._client._transport
        assert isinstance(transport, GuardedTransport)
        assert isinstance(transport._pool._network_backend, GuardedBackend)
        assert transport._pool._ssl_context.verify_mode == ssl.CERT_REQUIRED
        assert fetcher._client.trust_env is False  # no proxy or setting from the environment


# TLS -------------------------------------------------------------------------------------------


def test_tls_is_always_verified():
    context = tls_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2


def test_no_code_turns_tls_checks_off_or_speaks_plain_http():
    # "{http://...}" is the name of an XML namespace (Atom), not an address the collector contacts.
    forbidden = re.compile(r"verify\s*=\s*False|CERT_NONE|check_hostname\s*=\s*False|_create_unverified_context|(?<!\{)http://")
    found = [f"{path.name}: {match.group(0)}" for path in code_files() for match in forbidden.finditer(path.read_text(encoding="utf-8"))]
    assert found == []


# Time ------------------------------------------------------------------------------------------


def test_every_network_operation_has_a_timeout():
    with Fetcher(transport=httpx.MockTransport(lambda request: reply(200))) as fetcher:
        timeout = fetcher._client.timeout
    assert (timeout.connect, timeout.read, timeout.write, timeout.pool) == (20.0, 20.0, 20.0, 20.0)


def test_a_timeout_is_a_clean_failure():
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with Fetcher(transport=httpx.MockTransport(slow), sleep=lambda seconds: None) as fetcher:
        with pytest.raises(SourceError, match=r"^www\.cisa\.gov : ReadTimeout ; vérifiez votre connexion Internet, un pare-feu ou un proxy$"):
            fetcher.get(CISA)


def test_a_body_that_trickles_in_is_abandoned_after_60_seconds():
    now = [0.0]

    class Trickle(httpx.SyncByteStream):
        def __iter__(self):
            for _ in range(10):
                now[0] += 25  # one byte every 25 s: each read is under the 20 s... of the next one
                yield b"x"

    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=Trickle()))
    with Fetcher(transport=transport, clock=lambda: now[0], sleep=lambda seconds: None) as fetcher:
        with pytest.raises(SourceError, match="plus de 60 s, abandon ; vérifiez votre connexion Internet"):
            fetcher.get(CISA)
    assert now[0] <= 100


# Size and compression --------------------------------------------------------------------------


def zeros_gzipped(size: int) -> bytes:
    compressor = zlib.compressobj(9, zlib.DEFLATED, 16 + zlib.MAX_WBITS)
    block = bytes(1_000_000)
    parts = [compressor.compress(block) for _ in range(size // len(block))]
    return b"".join(parts) + compressor.flush()


def test_a_normal_gzip_answer_is_read():
    body = gzip.compress(b'{"vulnerabilities": []}')
    fetcher, seen = serving(lambda request, seen: reply(200, body, {"Content-Encoding": "gzip"}))
    with fetcher:
        assert fetcher.get(CISA) == b'{"vulnerabilities": []}'
    assert seen[0].headers["Accept-Encoding"] == "gzip"


def test_an_answer_over_20_mb_is_refused():
    fetcher, _ = serving(lambda request, seen: reply(200, bytes(config.MAX_RESPONSE_BYTES + 1)))
    with fetcher, pytest.raises(SourceError, match="réponse de plus de 20 Mo"):
        fetcher.get(CISA)


def test_a_declared_length_over_the_limit_is_refused_without_reading():
    class Never(httpx.SyncByteStream):
        def __iter__(self):
            raise AssertionError("the body was read")

    transport = httpx.MockTransport(lambda request: httpx.Response(200, headers={"Content-Length": str(10**10)}, stream=Never()))
    with Fetcher(transport=transport, sleep=lambda seconds: None) as fetcher, pytest.raises(SourceError, match="réponse de plus de"):
        fetcher.get(CISA)


def test_a_gzip_bomb_stops_at_the_limit():
    bomb = zeros_gzipped(300_000_000)  # 300 MB of zeros in about 300 kB
    assert len(bomb) < 400_000
    fetcher, _ = serving(lambda request, seen: reply(200, bomb, {"Content-Encoding": "gzip"}))
    with fetcher, pytest.raises(SourceError, match="réponse de plus de 20 Mo"):
        fetcher.get(CISA)


def test_a_gzip_bomb_never_fills_the_memory(monkeypatch):
    monkeypatch.setattr(config, "MAX_RESPONSE_BYTES", 1_000_000)
    bomb = zeros_gzipped(200_000_000)
    fetcher, _ = serving(lambda request, seen: reply(200, bomb, {"Content-Encoding": "gzip"}))
    tracemalloc.start()
    try:
        with fetcher, pytest.raises(SourceError, match="réponse de plus de"):
            fetcher.get(CISA)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 10_000_000  # the bomb holds 200 MB; at most about 1 MB was ever decompressed


@pytest.mark.parametrize("coding", ["gzip, gzip", "br", "deflate", "zstd", "compress", "gzip, br"])
def test_layers_of_compression_and_other_encodings_are_refused(coding):
    fetcher, _ = serving(lambda request, seen: reply(200, gzip.compress(gzip.compress(b"x")), {"Content-Encoding": coding}))
    with fetcher, pytest.raises(SourceError, match="encodage"):
        fetcher.get(CISA)


@pytest.mark.parametrize("body", [gzip.compress(b"x" * 10_000)[:-12], b"\x1f\x8b\x08\x00" + b"pas du gzip" * 50])
def test_a_cut_or_corrupt_gzip_is_a_clean_failure(body):
    fetcher, _ = serving(lambda request, seen: reply(200, body, {"Content-Encoding": "gzip"}))
    with fetcher, pytest.raises(SourceError, match="compressée"):
        fetcher.get(CISA)
