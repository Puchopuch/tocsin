# Tocsin

A public information service, in French and in English, about the cyberattacks that touch the
general public and businesses. Everything on the site is real: real attacks, real sources, updated by a
collector. **Tocsin** is a provisional name (`APP_NAME` in `frontend/src/config.js`).

| Folder | What it is |
|---|---|
| `collector/` | Python program that reads reliable sources and writes `frontend/public/data/cards.json` |
| `frontend/` | the static site, which shows that file and nothing else (see `frontend/README.md`) |

The collector works in two phases. **Phase 1, without AI**: the CISA catalogue of exploited
flaws and the CERT-FR alerts, plus the ransomware claims of ransomware.live with a key. **Phase 2,
with AI, only with a Mistral key**: articles of the specialised press read by Mistral; duplicates
are merged. Phase 3 (repeated runs, GitHub Actions) comes later.

**Honestly**: phase 2 and ransomware.live are tested with simulated answers only. No test, and no
check of this repository, ever called the real Mistral or the real ransomware.live: each user
brings their own keys.

## Install, once (Windows)

Python 3.12 or newer, started with `py`.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
```

`requirements.txt` pins every library, and every library they need, to an exact version
published before 5 November 2026. `requirements-dev.txt` adds pytest.

## Keys

The keys go in `.env`, which you fill in yourself and Git ignores. Never paste a key in a
conversation.

```powershell
copy .env.example .env
notepad .env
```

| Key | Needed for | Without it |
|---|---|---|
| `RANSOMWARE_LIVE_API_KEY` | ransomware claims (phase 1) | the run skips ransomware.live and says so |
| `MISTRAL_API_KEY` | press articles (phase 2) | not used yet |

The collector reads `.env` itself and only ever says whether a key is present; it never prints,
logs or stores its value.

## Run it

From the root of the repository:

```powershell
.venv\Scripts\python -m collector check-sources   # does each source answer?
.venv\Scripts\python -m collector run             # a full run (phase 1 for now)
.venv\Scripts\python -m collector run --phase 1   # without AI
.venv\Scripts\python -m collector run --dry-run   # writes nothing, shows what would be written
.venv\Scripts\python -m collector validate        # checks the existing cards.json
```

Then the site, which reads the cards just written:

```powershell
cd frontend
npm run dev
```

There is no other mode: `npm run dev` and `npm run build` read the real cards. Without a
collection, the site says "Aucune attaque recensée pour le moment" ("No attack recorded at the
moment" in English).

Each run ends with a summary: entries read per source, cards kept by level and by source, cards
rejected with their reason, cards held back, titles kept in French in the English version, AI
calls (none in phase 1), and what happened to `cards.json`.

## What phase 1 publishes

| Source | Taken | Card |
|---|---|---|
| CISA, Known Exploited Vulnerabilities | flaws added in the last 7 days | "Grave" in widespread software, otherwise "Significative" |
| CERT-FR, alerts | alerts of the last 7 days, with the CVE numbers of the feed and of the alert page | joins the CISA card of the same CVE, otherwise its own "Grave" card |
| ransomware.live PRO API | claims against organisations in France, recorded in the last 7 days | "Significative" at most, "Revendiqué, non confirmé" |

Every card is made of fixed sentences filled with fields of its source (brief, part B6). A
sentence longer than the limits of the site gives way to a generic one. What a source does not
say stays empty, and the site shows "Non communiqué" ("Not disclosed").

What a card says, without AI (`collector/flaws.py`, fixed tables in French and English):
- **CISA, method**: the type of flaw, read in the name the CISA gives it ("Code Injection",
  "Path Traversal"…), else in its CWE numbers (field `cwes`); unknown, the generic "Faille déjà
  exploitée par des attaquants".
- **CISA, impact**: the consequence the description names (code or command execution, privilege
  escalation, unauthorized access, data leak, denial of service…), "à distance" only when the
  text says "remote"; else "Non communiqué". Who can exploit the flaw ("un attaquant à distance,
  sans compte") is read in the sentence that names the consequence.
- **CISA, origin**: "Utilisée par des rançongiciels, selon la CISA" when the catalogue says
  `knownRansomwareCampaignUse: Known`; else unknown.
- **CERT-FR, targets and impact**: the lists "Systèmes affectés" and "Risques" of the alert page,
  products without their versions, risks through a table of the CERT-FR wording.
- **Summary**: one short sentence of its own ("Injection de code dans REDCap : un attaquant sans
  compte peut exécuter du code."), then the date. The CISA and the CERT-FR are introduced once, in
  "Méthode et sources", not on every card.
- **Kind**: `kind` is `faille` for a flaw, `attaque` for an attack; the daily sentence of the site
  says "alertes", not "attaques", unless every card counted is an attack.

### In French and in English

The collector writes each text of a card in both languages, `{ "fr": "…", "en": "…" }`, without
any translation service: every fixed sentence exists in French and in English, and the names of
products, groups and organisations are the same in both. A shorter variant is chosen only if it
fits the limits in both languages, so that both versions say the same thing.

The title of a CERT-FR alert is the only text taken word for word from a French source. It is
translated in its usual forms only ("Vulnérabilité dans X", "Multiples vulnérabilités dans les
produits X"…), and only when the product name holds no French word. Otherwise translating it
would mean inventing: the English version keeps the French title, the card carries
`untranslated: ["title"]`, the site marks that title as French, and the run summary lists the
card.

The collector writes plain spaces; the site adds French typography to French texts only.

## What phase 2 publishes, with a Mistral key

Articles of BleepingComputer, The Record, ZATAZ and LeMagIT (`config.PRESS_FEEDS`), of the last 7
days, that speak of an attack (a word of `config.DOMAIN_WORDS`), newest first. **The AI reads, the
code judges** (`collector/press.py`, `collector/facts.py`):

1. The text of the article is read on its page when robots.txt allows it, visible text only
   (`collector/article.py`: no comment, attribute, script, hidden element or invisible character),
   else the summary of the feed; cut to 8,000 characters.
2. **First call**: the AI extracts facts (`Facts`), each with a quote of 3 to 25 words. The code
   keeps a fact only when its quote is in the article word for word, after normalising spaces,
   apostrophes, quotes and dashes (never approximately), and says what the fact says: the name or
   the number is in the quote, a fact that raises the level holds a word of its kind ("santé",
   "hôpital"...). A country is kept only when the quote names an authority of a closed list
   (`config.AUTHORITIES`: ANSSI, CERT-FR, CISA, FBI, NCSC, Europol, a government...).
3. **The code** sets the level from the facts kept (grid B8), the statuses, the audience, the
   links (those of the feed) and the dates. A victim that may be a person is held back.
4. **Second call**: the AI writes the texts of the card in French and in English from the facts
   kept only, never from the article. "Que faire" comes from the actions recommended by the
   article, each one proven by a quote. Too long: asked once more, then refused. A text holding a
   link, an e-mail, a phone number, an IBAN, a wallet address, or a number that is not in the
   facts, is refused.
5. With the calls left, the AI translates into French the text of the CISA for its cards, adding
   nothing; the English stays the text of the CISA.

Every card written or translated by the AI says so on the card itself, and keeps the dated model
(`config.MISTRAL_MODEL`, never `-latest`) and the version of the prompts (`collector/prompts/`).
At most 40 calls per run (`--max-ai-calls`), newest articles first; after HTTP 429, a growing wait
then a clean stop; an answer is kept 30 days in `state.db`, so that the same text never costs a
second call. Only the instructions and the text to read are sent to Mistral.

**Duplicates** (`collector/cluster.py`): a press card citing the CVE of a CISA or CERT-FR card
joins it as one more source; press cards and claims about the same victim (normalised name)
within 7 days make one card, with all their sources.

## Rules the code applies

- Nothing invented: each piece of information comes from a source; a source that gives a date
  without a time gets a date without a time.
- Links: https only, to an ordinary host name, and each source to its own domain (CISA to
  cisa.gov, NVD to nvd.nist.gov, CERT-FR to cert.cyber.gouv.fr, ransomware.live to
  ransomware.live). Never `javascript:`, `data:`, `vbscript:`, `file:`, a link without scheme,
  a user name or password, a port, a `.onion` or `xn--` name, an IP address, a space, a quote or
  an angle bracket, whatever the case or the encoding. Of each ransomware.live entry, only the
  victim, the country, the group, the date and the ransomware.live page are kept; `post_url`,
  screenshots and the rest are dropped on reading.
- A claim never goes above "Significative" (safety net applied last, then checked again).
- Lengths, in each language: title of 10 words at most; victim, method and loot of 45
  characters; "Suis-je concerné ?" and "Que faire" of 75; any text of 2,000 characters at most.
  A card that breaks a rule, or misses a language, is rejected and logged.
- No personal data: no e-mail address or phone number in a card, in either language, and a claim
  whose victim may be a person is held back (see "Choices").
- A failure never empties the site, nor makes it lie about the time: if a source fails, if the
  result is empty while the previous file had cards, or if the file cannot be written, the
  previous `cards.json` stays, with its cards and the time of the last complete collection.
- The file is written to a temporary file, flushed to disk, then renamed: a write cut in the
  middle leaves the previous file whole.

## Security

**Requests** (`collector/sources/__init__.py`). The collector contacts four sites only
(`ALLOWED_HOSTS` in `collector/config.py`), over https, on their usual port. It resolves their
names itself and refuses a site whose name gives any private, local, link-local (such as the
cloud metadata address 169.254.169.254), multicast or reserved address, in IPv4 or IPv6, IPv4
written as IPv6 included; it then connects to an address it checked, while TLS still checks the
certificate against the name. TLS is always verified (certifi, TLS 1.2 at least), and no proxy or
setting is taken from the environment. Each redirect is checked the same way, and 3 at most are
followed. Each network operation has 20 s, each request 60 s in all. An answer is read 20 MB at
most once decompressed; only gzip is accepted, decompressed piece by piece, so that a compression
bomb stops at the limit.

**What the sources send.** The CERT-FR feed is read with defusedxml and no DTD at all, so that
neither an XXE nor a "billion laughs" can go through. Broken JSON, XML or HTML, deep nesting,
huge texts (more than 300 characters for a name or a title, 5,000 for a description), NUL bytes
and invalid Unicode: the entry is skipped and counted, the collection goes on, and the error
names a count, never the content. Control, invisible and bidi characters (U+202E, U+2066 to
U+2069, zero-width spaces...) are taken out of every text, which is then normalised (NFC);
`cards.json` refuses any that would remain.

**Keys.** A key is read from `.env` or the environment, held as a `SecretStr` (shown as
`**********`), sent in its header to its own API only (ransomware.live: `api-pro.ransomware.live`),
never through a redirect, and never kept in `state.db`. Errors name the site and the kind of
failure, never a request or its headers.

**SQLite.** Every query is a fixed text with placeholders: a value never becomes SQL.
`state.db` is only a cache: deleted or damaged, it starts again empty, and the next collection
gives the same cards.

## Choices

- **User-Agent** `Tocsin-collecteur/0.1`, without the repository URL while the repository is
  private: the URL would only show the owner's account and lead to a missing page. It joins the
  User-Agent when the repository is public. Timeout 20 s, one request per second per site,
  `ETag` and `Last-Modified` kept in `collector/state.db`.
- **Widespread software**: the list of the brief, plus Check Point, Synology and QNAP; VMware is
  now filed by the CISA under Broadcom; of Apache, only HTTP Server, Tomcat and Log4j.
- **General public**: a card also concerns the general public when the source names a consumer
  product: browsers (Chrome, Firefox, Safari, Edge), systems (Windows, macOS, iOS, Android),
  common apps (WhatsApp, Telegram…) and equipment found at home: network storage (Synology,
  QNAP, WD My Cloud), boxes and routers (TP-Link, D-Link, Netgear, ASUS, Livebox, Freebox…),
  Plex Media Server. A vendor is required when needed, so that Cisco IOS is not Apple iOS. The
  list is in `collector/config.py`.
- **Product names**: when a product gives its abbreviation in brackets, the title and the short
  sentences use it, after the vendor when the vendor is a single word: "Faille exploitée dans
  Synology DSM", "Faille exploitée dans REDCap". Brackets that only qualify a product, such as
  "(Chromium-based)", do not count. The summary keeps the full name given by the source.
- **Exploited flaws**: `exploited` is `true` only when a source confirms it, that is the CISA
  catalogue of exploited flaws. On the same day and at the same level, such a card comes before
  the others, in `cards.json` as on the site.
- **Names that look like a person** ("Dr", "Maître", a common first name followed by a name): the
  claim is not published. Those names are written only to `collector/logs/collector.log`, local
  and ignored by Git; the console shows counts only.
- **CERT-FR cards** never say "exploitée": an alert may report a flaw that nobody has exploited
  yet (CERTFR-2026-ALE-017 only mentions a public proof of concept). Method "Faille signalée par
  le CERT-FR", impact "Non communiqué", and `exploited: false`, unless the CISA lists the same
  CVE: the alert then joins that card.
- **Claims**: `reliability: "confirme"` (ransomware.live did record the claim) with the
  `revendique` status for the victim and the group (the attack itself is not confirmed), so that
  the site shows "Revendiqué, non confirmé" and not "Rumeur".
- **A source down**: when a source fails, the whole previous file stays rather than a mix of new
  and old cards, so that "Mis à jour à" never claims a collection that did not happen. Without a
  previous file (first collection), the cards of the other sources are written, and the summary
  says so. The run ends with code 1 whenever a source failed.
- **Names of the sources**: a card may only cite a source of `SOURCE_DOMAINS`
  (`collector/config.py`), with a link to its domain. Phase 2 will add the press sites there.
- **No proxy**: the collector ignores the proxy settings of the environment (`trust_env=False`),
  so that no setting from outside can send its requests elsewhere.
- **Libraries**: httpx, pydantic, python-dotenv, defusedxml (0.7.1, the last stable version).
  feedparser, rapidfuzz and trafilatura will come with the phases that need them.

## Tests

```powershell
.venv\Scripts\python -m pytest
```

They never reach the network and never touch the real `.env`, `state.db`, journal or
`cards.json`. The samples of `collector/tests/data/` are real extracts of the CISA catalogue and
of the CERT-FR feed and pages. The ransomware.live sample is entirely invented, groups included,
so that no real organisation or group is named in the repository.

The security tests are in `test_network.py` (sites, addresses, redirects, TLS, time and size
limits, compression bombs), `test_inputs.py` (XXE, billion laughs, broken inputs, hidden
characters, links, SQL) and `test_secrets_resilience.py` (keys, interrupted writes, sources down,
`state.db` deleted or damaged). `collector/tests/data/links.json` holds the links to refuse and
to accept: the site checks the same cases (`npm run check`). The tests contain IP addresses on
purpose (127.0.0.1, 169.254.169.254, 8.8.8.8...): loopback, private, metadata and public
resolver addresses, none of them personal.

## Never committed

`.env`, `.venv/`, `collector/state.db`, `collector/logs/`, `frontend/public/data/cards.json` (it
names real organisations; how to publish it will be decided later) and `docs/*.pdf`.
