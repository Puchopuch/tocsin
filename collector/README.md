# Tocsin, collector

The Python program that reads the sources and writes `frontend/public/data/cards.json`. How to
install and run it: the [main README](../README.md). This file records how it works and why.

## Layout

```
collector/
  __main__.py        command line: check-sources, run, validate; the summary of each run
  config.py          sources, allowed sites, limits, lists (widespread software, consumer products...)
  models.py          pydantic models: entries of the sources, Card (the format of frontend/README.md)
  sources/
    __init__.py      the guarded HTTP layer (Fetcher): allowed sites, public addresses, TLS, limits
    kev.py           CISA, Known Exploited Vulnerabilities
    certfr.py        CERT-FR alerts and their pages (CVE links, affected systems, risks)
    ransomware_live.py  ransomware.live PRO API (key)
    rss.py           press feeds (phase 2)
  cards.py           phase 1 cards, fixed sentences in French and English
  flaws.py           fixed tables: types of flaws, consequences, CERT-FR risks
  article.py         the visible text of a web page
  ai.py              calls to Mistral (key, budget, cache, strict schema)
  facts.py           facts of an article, their quotes checked, the level computed (grid B8)
  press.py           phase 2 cards
  cluster.py         duplicates merged
  severity.py        phase 1 levels and the claim safety net
  store.py           state.db: HTTP cache and AI answers
  output.py          validation and atomic writing of cards.json
  text.py            text helpers: cleaning, dates, French elision
  prompts/           the instructions of the AI, versioned
  tests/             pytest, without network
```

## Choices

- **User-Agent** `Tocsin-collecteur/1.0.0 (+https://github.com/Puchopuch/tocsin)` (`VERSION`
  in `config.py`); timeout 20 s per network operation, 60 s per request; one request per second
  per site; `ETag` and `Last-Modified` kept in `state.db`.
- **Widespread software**: Microsoft, Apple, Google, Mozilla, Cisco, Fortinet, Ivanti, Citrix,
  VMware, Palo Alto Networks, Oracle, Adobe, SAP, Atlassian, SonicWall, Juniper, F5, Linux, plus
  Check Point, Synology and QNAP; VMware is now filed by the CISA under Broadcom; of Apache, only
  HTTP Server, Tomcat and Log4j.
- **General public**: a card also concerns the general public when the source names a consumer
  product: browsers, systems of computers and phones, common apps, and equipment found at home
  (network storage, boxes and routers, Plex Media Server). A vendor is required when needed, so
  that Cisco IOS is not Apple iOS. For a press card: when the facts kept speak of people affected
  or of their data.
- **Product names**: when a product gives its abbreviation in brackets, the title and the short
  sentences use it ("Synology DSM", "REDCap"); the technical details keep the full name.
- **Exploited flaws**: `exploited` is `true` only for the CISA catalogue. On the same day and at
  the same level, such a card comes first. CERT-FR cards never say "exploitée".
- **Claims**: `reliability: "confirme"` (ransomware.live did record the claim) with the
  `revendique` status, so that the site shows "Revendiqué, non confirmé". Once a victim confirms
  the attack, the claim of a group only names a presumed author, and no longer caps the level.
- **Names that look like a person** ("Dr", "Maître", a common first name followed by a name): the
  card is not published, for claims and for the victims found by the AI. Those names go only to
  `collector/logs/collector.log`.
- **A source down**: the whole previous file stays rather than a mix of new and old cards, so that
  "Mis à jour à" never claims a collection that did not happen. Without a previous file, the cards
  of the other sources are written. The run ends with code 1 whenever a source failed. A refused
  key is not a source down: it is skipped with a clear message.
- **Names of the sources**: a card may only cite a source of `SOURCE_DOMAINS`, with a link to its
  domain.
- **No proxy**: the collector ignores the proxy settings of the environment (`trust_env=False`).
- **Model of the AI**: `mistral-small-2603` (Mistral Small 4, version 26.03 of the Mistral
  documentation), never "-latest", so that each card says which model wrote it; `check-sources`
  says when Mistral no longer offers it. Temperature 0.1, strict JSON schema.
- **Libraries**: httpx, pydantic, python-dotenv, defusedxml. No feedparser (the feeds are read
  with defusedxml, without DTD, like the CERT-FR feed), no trafilatura (the visible text is read
  with the standard library, which also drops what a page hides), no Mistral SDK (the API is called
  through the guarded HTTP layer), no rapidfuzz (duplicates compare normalised names exactly).
  Exact versions, published before 5 November 2026.

## In French and in English

Each text of a card is `{ "fr": "…", "en": "…" }`. Phase 1 writes both from fixed sentences; a
shorter variant is chosen only if it fits the limits in both languages. The title of a CERT-FR
alert is translated in its usual forms only; otherwise it stays in French, with
`untranslated: ["title"]`. Phase 2 cards are written in both languages by the AI. The collector
writes plain spaces; the site adds French typography to French texts only.

## Security, in detail

- **Requests** (`sources/__init__.py`): https only, to `ALLOWED_HOSTS` only, usual port, no
  credentials. The name is resolved here; a site whose name gives any private, local, link-local
  (169.254.169.254), multicast or reserved address is refused, IPv4 written as IPv6 included; the
  connection goes to a checked address, while TLS checks the certificate against the name. TLS
  1.2 at least, certifi. Redirects checked the same way, 3 at most. 20 MB at most once
  decompressed, gzip only, decompressed piece by piece.
- **Inputs**: defusedxml without DTD; broken JSON, XML or HTML, deep nesting, huge texts, NUL bytes
  and invalid Unicode skip the entry, counted; control, invisible and bidi characters removed,
  Unicode normalised (NFC). HTML is read by the parser of the standard library (`html.parser`),
  never by a regular expression: the text of articles, the lists and the cve.org links of CERT-FR
  pages (a link in a comment, a script or plain text is not a link; capitals, line breaks and
  entities change nothing).
- **Links**: https and an ordinary host name only: never `javascript:`, `data:`, `vbscript:`,
  `file:`, `//`, credentials, a port, `.onion` or `xn--`, an IP address, a space, a quote or an
  angle bracket, whatever the case or the encoding (`tests/data/links.json`, checked by the site
  too).
- **Keys**: `SecretStr`, sent in their header to their own API only, never through a redirect,
  never in `state.db`; errors name a site and a kind of failure, never a request.
- **SQLite**: fixed queries with placeholders. `state.db` is a cache: deleted or damaged, it starts
  again empty and gives the same cards.
- **The AI**: see the main README, "Phase 2". Its answers follow a strict schema; the code checks
  every quote, decides the level, links and statuses, and refuses links, e-mails, phone numbers,
  IBANs, wallet addresses and numbers absent from the facts in its texts.

## Tests

`pytest` runs them all (`pytest.ini`): no network, no DNS (`tests/conftest.py`), no real `.env`,
`state.db`, journal or `cards.json`. Tests slower than one second are listed at the end of a run.

| File | What it checks |
|---|---|
| `test_cards.py` | phase 1 cards, in both languages |
| `test_sources.py`, `test_fetcher.py`, `test_cli.py`, `test_output.py` | sources, HTTP layer, command line, cards.json |
| `test_network.py` | sites, addresses, redirects, TLS, time and size limits, compression bombs |
| `test_inputs.py` | XXE, billion laughs, broken inputs, HTML in every spelling, hidden characters, links, SQL |
| `test_secrets_resilience.py` | keys, interrupted writes, sources down, state.db deleted or damaged |
| `test_phase2.py`, `test_phase2_cli.py` | the press and the AI, simulated: traps, quotes, budget, cache, keys |

The samples of `tests/data/`: real extracts of the CISA catalogue and of the CERT-FR feed and
pages; invented press articles and ransomware.live answers, names included. The tests hold IP
addresses on purpose (127.0.0.1, 169.254.169.254, 8.8.8.8...): loopback, private, metadata and
public resolver addresses, none of them personal.
