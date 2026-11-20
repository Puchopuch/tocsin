# Tocsin

A public information service, in French, about the cyberattacks that touch the general public
and businesses. Everything on the site is real: real attacks, real sources, updated by a
collector. **Tocsin** is a provisional name (`APP_NAME` in `frontend/src/config.js`).

| Folder | What it is |
|---|---|
| `collector/` | Python program that reads reliable sources and writes `frontend/public/data/cards.json` |
| `frontend/` | the static site, which shows that file and nothing else (see `frontend/README.md`) |

The collector is built in three phases. **Phase 1 (without AI) is done**: the CISA catalogue of
exploited flaws, the CERT-FR alerts and the ransomware claims of ransomware.live. Phase 2 (press
articles read by AI) and phase 3 (grouping, repeated runs, GitHub Actions) come next.

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
collection, the site says "Aucune attaque recensée pour le moment".

Each run ends with a summary: entries read per source, cards kept by level and by source, cards
rejected with their reason, cards held back, AI calls (none in phase 1), and what happened to
`cards.json`.

## What phase 1 publishes

| Source | Taken | Card |
|---|---|---|
| CISA, Known Exploited Vulnerabilities | flaws added in the last 7 days | "Grave" in widespread software, otherwise "Significative" |
| CERT-FR, alerts | alerts of the last 7 days, with the CVE numbers of the feed and of the alert page | joins the CISA card of the same CVE, otherwise its own "Grave" card |
| ransomware.live PRO API | claims against organisations in France, recorded in the last 7 days | "Significative" at most, "Revendiqué, non confirmé" |

Every card is made of fixed sentences filled with fields of its source (brief, part B6). A
sentence longer than the limits of the site gives way to a generic one. What a source does not
say stays empty, and the site shows "Non communiqué".

## Rules the code applies

- Nothing invented: each piece of information comes from a source; a source that gives a date
  without a time gets a date without a time.
- Links come from the code: http(s) only, never a `.onion` address, never the site of a ransomware
  group. Of each ransomware.live entry, only the victim, the country, the group, the date and the
  ransomware.live page are kept; `post_url`, screenshots and the rest are dropped on reading.
- A claim never goes above "Significative" (safety net applied last, then checked again).
- Lengths: title of 10 words at most; victim, method and loot of 45 characters; "Suis-je
  concerné ?" and "Que faire" of 75. A card that breaks a rule is rejected and logged.
- No personal data: no e-mail address or phone number in a card, and a claim whose victim may be
  a person is held back (see "Choices").
- A failure never empties the site: if every source fails, or if the result is empty while the
  previous file had cards, the previous `cards.json` stays.
- The file is written to a temporary file, then renamed.

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
- **Libraries**: httpx, pydantic, python-dotenv. feedparser, rapidfuzz and trafilatura will come
  with the phases that need them; the single CERT-FR feed is read with the standard library.

## Tests

```powershell
.venv\Scripts\python -m pytest
```

They never reach the network and never touch the real `.env`, `state.db`, journal or
`cards.json`. The samples of `collector/tests/data/` are real extracts of the CISA catalogue and
of the CERT-FR feed and pages. The ransomware.live sample is entirely invented, groups included,
so that no real organisation or group is named in the repository.

## Never committed

`.env`, `.venv/`, `collector/state.db`, `collector/logs/`, `frontend/public/data/cards.json` (it
names real organisations; how to publish it will be decided later) and `docs/*.pdf`.
