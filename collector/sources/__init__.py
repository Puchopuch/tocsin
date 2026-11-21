"""Polite and guarded access to the sources.

Polite (B4): a User-Agent naming the project, at most one request per second to the same site, and
ETag / Last-Modified so that a file that has not changed is not downloaded again.

Guarded:
- https only, to the sites of config.ALLOWED_HOSTS only, on their usual port, without user name or
  password; each redirect is checked the same way, and 3 redirects at most are followed;
- public addresses only. The name of the site is resolved here and every address it gives is
  checked: private, local, link-local (such as the cloud metadata address 169.254.169.254),
  multicast and reserved addresses are refused, in IPv4 and in IPv6, IPv4 written as IPv6
  (::ffff:127.0.0.1) included. The connection then goes to an address that was checked, so that a
  second DNS answer cannot slip a private one in between;
- TLS always verified, against the authorities of certifi, TLS 1.2 at least; no proxy and no
  setting taken from the environment;
- 20 s at most per network operation and 60 s per request; 20 MB at most once decompressed, gzip
  only, decompressed piece by piece so that a compression bomb stops at the limit;
- a key goes in its header to its own site only, is never kept in state.db, and never follows a
  redirect.
"""

from __future__ import annotations

import ipaddress
import json
import socket
import ssl
import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import certifi
import httpcore
import httpx
from pydantic import SecretStr

from .. import config
from ..store import Store


class SourceError(Exception):
    """A source could not be read. The message names the site and the reason, never a key."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class ApiKey:
    """A key, the header that carries it and the only site it may be sent to. Printed, logged or
    put in an error, its value shows as **********."""

    header: str
    host: str
    secret: SecretStr
    prefix: str = ""  # "Bearer " for Mistral

    def value(self) -> str:
        return self.prefix + self.secret.get_secret_value()


def window_start(now: datetime) -> datetime:
    """Start of the 7-day window: midnight UTC, 7 days ago. Whole days, so that a source giving
    only a date counts the same way as a source giving a time."""
    day = (now.astimezone(timezone.utc) - timedelta(days=config.WINDOW_DAYS)).date()
    return datetime.combine(day, datetime.min.time(), timezone.utc)


# Addresses -------------------------------------------------------------------------------------

NAT64 = ipaddress.IPv6Network("64:ff9b::/96")


class BlockedAddress(httpcore.ConnectError):
    """The name of a site gave an address that is not on the public internet."""


def is_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True for an address of the public internet. An IPv4 address carried by an IPv6 one
    (::ffff:127.0.0.1, 6to4, Teredo, NAT64) must be public too."""
    if isinstance(address, ipaddress.IPv6Address):
        carried = [address.ipv4_mapped, address.sixtofour]
        if address.teredo:
            carried.append(address.teredo[1])
        if address in NAT64:
            carried.append(ipaddress.IPv4Address(int(address) & 0xFFFFFFFF))
        if address.is_site_local or any(inner is not None and not is_public(inner) for inner in carried):
            return False
    return address.is_global and not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def public_addresses(host: str, port: int, resolve: Callable = socket.getaddrinfo) -> list[str]:
    """The addresses of the site. If any of them is not public, the site is refused as a whole."""
    try:
        answers = resolve(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        raise httpcore.ConnectError("nom introuvable") from None
    addresses: list[str] = []
    for *_, sockaddr in answers:
        try:
            address = ipaddress.ip_address(str(sockaddr[0]).split("%", 1)[0])
        except ValueError:
            raise BlockedAddress("adresse illisible") from None
        if not is_public(address):
            raise BlockedAddress(f"adresse non publique : {address}")
        if str(address) not in addresses:
            addresses.append(str(address))
    if not addresses:
        raise httpcore.ConnectError("aucune adresse")
    return addresses


class GuardedBackend(httpcore.NetworkBackend):
    """Opens connections to checked public addresses only (see public_addresses)."""

    def __init__(self, resolve: Callable = socket.getaddrinfo, backend: httpcore.NetworkBackend | None = None) -> None:
        self._resolve = resolve
        self._backend = backend or httpcore.SyncBackend()

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        failure: Exception = httpcore.ConnectError("aucune adresse")
        for address in public_addresses(host, port, self._resolve):
            try:
                # TLS still checks the certificate against the name of the site, not the address.
                return self._backend.connect_tcp(
                    address, port, timeout=timeout, local_address=local_address, socket_options=socket_options
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as error:
                failure = error
        raise failure

    def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise httpcore.ConnectError("socket local refusé")

    def sleep(self, seconds: float) -> None:
        self._backend.sleep(seconds)


def tls_context() -> ssl.SSLContext:
    """Certificate and name of the site always checked, against the authorities of certifi; TLS
    1.2 at least."""
    context = ssl.create_default_context(cafile=certifi.where())
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


class GuardedTransport(httpx.HTTPTransport):
    """The transport of httpx, whose connections go through GuardedBackend."""

    def __init__(self, backend: httpcore.NetworkBackend | None = None) -> None:
        context = tls_context()
        super().__init__(verify=context, trust_env=False)
        # httpx offers no choice of network backend: its connection pool is built again, with the
        # same settings and GuardedBackend. test_network checks that this pool is the one used.
        self._pool = httpcore.ConnectionPool(
            ssl_context=context,
            network_backend=backend or GuardedBackend(),
            max_connections=10,
            max_keepalive_connections=5,
            keepalive_expiry=5.0,
            http1=True,
            http2=False,
            retries=0,
        )


# Requests --------------------------------------------------------------------------------------


class Fetcher:
    def __init__(
        self,
        store: Store | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        allowed_hosts: frozenset[str] = config.ALLOWED_HOSTS,
    ) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": config.USER_AGENT, "Accept-Encoding": "gzip"},
            timeout=config.TIMEOUT_SECONDS,
            follow_redirects=False,
            trust_env=False,
            transport=transport if transport is not None else GuardedTransport(),
        )
        self._allowed = frozenset(allowed_hosts)
        self._store = store
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, float] = {}
        self.requests = 0

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _pause(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            wait = config.SECONDS_BETWEEN_REQUESTS - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._last[host] = self._clock()

    def _check(self, url: httpx.URL) -> None:
        """https, a site of the list, its usual port, no user name or password."""
        if url.scheme != "https" or url.userinfo or url.port not in (None, 443) or url.host not in self._allowed:
            raise SourceError(f"{url.host[:100] or '?'} : adresse refusée (https et sites prévus seulement)")

    def get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        cache: bool = True,
        key: ApiKey | None = None,
    ) -> bytes:
        """The body found at this address, decompressed. With a key, the request goes to the site
        of the key only, is not kept in the cache and follows no redirect."""
        try:
            target = httpx.URL(url, params=params)
        except (httpx.InvalidURL, TypeError, ValueError):
            raise SourceError("adresse illisible") from None
        self._check(target)
        sent = dict(headers or {})
        if key is not None:
            if target.host != key.host:
                raise SourceError(f"{target.host} : la clé {key.header} n'est envoyée qu'à {key.host}")
            sent[key.header] = key.value()
            cache = False
        cached = self._store.cached(str(target)) if cache and self._store else None
        if cached is not None:
            if cached.etag:
                sent["If-None-Match"] = cached.etag
            if cached.last_modified:
                sent["If-Modified-Since"] = cached.last_modified

        address, redirects = target, 0
        while True:
            response = self._send(address, sent)
            try:
                if response.has_redirect_location:
                    if key is not None:
                        raise SourceError(
                            f"{address.host} : redirection refusée, une clé ne suit jamais une redirection",
                            response.status_code,
                        )
                    redirects += 1
                    if redirects > config.MAX_REDIRECTS:
                        raise SourceError(f"{address.host} : plus de {config.MAX_REDIRECTS} redirections")
                    address = self._following(address, response)
                    continue
                if response.status_code == 304 and cached is not None:
                    return cached.body
                if response.status_code >= 300:
                    raise SourceError(f"{address.host} : HTTP {response.status_code}", response.status_code)
                body = self._read(address, response)
                etag, modified = response.headers.get("ETag"), response.headers.get("Last-Modified")
            finally:
                response.close()
            if cache and self._store:
                self._store.save(str(target), etag, modified, body)
            return body

    def post_json(self, url: str, payload: dict, *, key: ApiKey) -> bytes:
        """A JSON payload sent to an API with its key: the same guards as get (listed site, https,
        public addresses, time and size limits), never a redirect, never cached. An HTTP error
        raises SourceError with its status (401 and 403: key refused; 429: too many requests)."""
        try:
            target = httpx.URL(url)
        except (httpx.InvalidURL, TypeError, ValueError):
            raise SourceError("adresse illisible") from None
        self._check(target)
        if target.host != key.host:
            raise SourceError(f"{target.host} : la clé {key.header} n'est envoyée qu'à {key.host}")
        headers = {key.header: key.value(), "Content-Type": "application/json", "Accept": "application/json"}
        response = self._send(target, headers, method="POST", content=json.dumps(payload).encode("utf-8"))
        try:
            if 300 <= response.status_code:
                raise SourceError(f"{target.host} : HTTP {response.status_code}", response.status_code)
            return self._read(target, response)
        finally:
            response.close()

    def _send(self, address: httpx.URL, headers: dict[str, str], method: str = "GET", content: bytes | None = None) -> httpx.Response:
        self._pause(address.host)
        request = self._client.build_request(method, address, headers=headers, content=content)
        try:
            response = self._client.send(request, stream=True)
        except httpx.InvalidURL:  # httpx reads the Location of a redirect even when it does not follow it
            raise SourceError(f"{address.host} : redirection illisible, refusée") from None
        except httpx.HTTPError as error:
            raise SourceError(f"{address.host} : {why(error)}") from None
        self.requests += 1
        return response

    def _following(self, address: httpx.URL, response: httpx.Response) -> httpx.URL:
        try:
            following = address.join(response.headers["Location"])
        except (httpx.InvalidURL, KeyError, TypeError, ValueError):
            raise SourceError(f"{address.host} : redirection illisible") from None
        self._check(following)
        return following

    def _read(self, address: httpx.URL, response: httpx.Response) -> bytes:
        """The body, decompressed piece by piece: never more than MAX_RESPONSE_BYTES in memory,
        never longer than TOTAL_SECONDS."""
        limit = config.MAX_RESPONSE_BYTES
        too_big = f"{address.host} : réponse de plus de {limit // 1_048_576} Mo, refusée"
        declared = response.headers.get("Content-Length", "").strip()
        if declared.isdigit() and int(declared) > limit:
            raise SourceError(too_big)
        codings = [part.strip().lower() for part in response.headers.get("Content-Encoding", "").split(",")]
        codings = [coding for coding in codings if coding and coding != "identity"]
        if codings not in ([], ["gzip"], ["x-gzip"]):
            raise SourceError(f"{address.host} : encodage {', '.join(codings)[:40]} refusé")
        inflate = zlib.decompressobj(16 + zlib.MAX_WBITS) if codings else None
        deadline = self._clock() + config.TOTAL_SECONDS
        body = bytearray()
        received = 0
        try:
            for chunk in response.iter_raw():
                received += len(chunk)
                if received > limit:
                    raise SourceError(too_big)
                if self._clock() > deadline:
                    raise SourceError(f"{address.host} : plus de {config.TOTAL_SECONDS:.0f} s, abandon")
                if inflate is None:
                    body += chunk
                # The output of each step is capped, so that the rest waits in unconsumed_tail.
                while inflate is not None and chunk and not inflate.eof:
                    body += inflate.decompress(chunk, limit + 1 - len(body))
                    chunk = inflate.unconsumed_tail
                    if len(body) > limit:
                        raise SourceError(too_big)
                if len(body) > limit:
                    raise SourceError(too_big)
        except httpx.HTTPError as error:
            raise SourceError(f"{address.host} : {why(error)}") from None
        except zlib.error:
            raise SourceError(f"{address.host} : réponse compressée illisible") from None
        if inflate is not None and not inflate.eof:
            raise SourceError(f"{address.host} : réponse compressée incomplète")
        return bytes(body)


def why(error: httpx.HTTPError) -> str:
    """The kind of error only: its details could repeat the request and its headers."""
    if isinstance(error.__cause__, BlockedAddress):
        return "adresse non publique, refusée"
    return type(error).__name__
