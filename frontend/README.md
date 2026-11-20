# Tocsin, frontend

A public information service, in French and in English, about the cyberattacks that touch the
general public and businesses: calm and clear, neither a security dashboard nor a "hacker" look. It quotes
CERT-FR and other sources but must never look official (no Marianne font, no blue-white-red).

**Tocsin** is a provisional name. It lives in one constant, `APP_NAME` in `src/config.js`;
`vite.config.js` also writes it into the page title.

The site only reads `data/cards.json`, written by the collector (`collector/` at the root of the
repository, see the main README). It calls no API and holds no secret. Everything it shows is
real: there is no demo mode and no fictional card.

## Run it

Node.js 20.19 or newer.

```sh
npm ci               # install the pinned dependency tree
npm run dev          # http://localhost:5173, with the real cards of public/data/cards.json
npm run build        # the site, in dist/ (public/data/cards.json is copied next to index.html)
npm run preview      # serves dist/ locally
npm run check        # automated browser checks and screenshots, see "Checks"
```

The collector writes `public/data/cards.json`, which Git ignores: it names real organisations.
Run it first (`.venv\Scripts\python -m collector run` at the root); without that file, the site
says "Aucune attaque recensée pour le moment" ("No attack recorded at the moment").

Dependencies are pinned to exact versions. Add one only with
`npm install --before=2026-11-05 --save-exact <package>`.

## One mode

`npm run dev` and `npm run build` both read the real `data/cards.json`. Test cards live in
`scripts/fixtures.mjs` and reach the page only during `npm run check`, which intercepts the
request for `data/cards.json`; a check verifies that none of them, and no word such as "démo",
"simulation", "fictif" or "fictional", reaches the built site.

| Situation | The page shows |
|---|---|
| `data/cards.json` holds cards | the cards of the last seven days |
| the file holds no attack | "Aucune attaque recensée pour le moment", and the time of the collection |
| no file (404, or an HTML page in its place) | "Aucune attaque recensée pour le moment", no time |
| the file cannot be read | an error message: saying "no attack" would be inventing |

The file is read again every 5 minutes and when the tab comes back into view; a refresh that
fails keeps what is shown.

## Two languages

The site is in French and in English; "FR | EN" in the header switches the whole page at once.

- **Default**: the first of French or English among the languages of the browser, English if
  neither is there. The choice is then kept in `localStorage` (`tocsin.lang`), which accepts
  only `fr` or `en`: any other stored value is ignored, and a browser that refuses storage still
  switches, without remembering.
- `<html lang>` and the page title follow the language.
- **Interface texts** live in `src/lib/i18n.js`, one dictionary per language with the same keys;
  a check fails if a key is missing or empty in either. Levels: Mineure / Minor, Significative /
  Significant, Grave / Severe, Critique / Critical. Missing information: "Non communiqué" /
  "Not disclosed".
- **Card texts** come from the collector in both languages (see the format below): the site
  translates nothing.
- **French typography** (typographic apostrophe, non-breaking space before `: ; ! ?` and inside
  « », narrow non-breaking space between thousands) applies to French only.
- **Dates** follow the language: "07 h 42", "aujourd'hui", "hier", "18 nov.", "Mis à jour à
  15 h 30" in French; "07:42", "today", "yesterday", "18 Nov", "Updated at 15:30" in English.

## Data format: `data/cards.json`

```json
{
  "generated_at": "2026-11-20T14:30:46Z",
  "attacks": [{ "id": "…", "title": { "fr": "Faille exploitée dans REDCap", "en": "Exploited flaw in REDCap" } }]
}
```

`generated_at` is the UTC time of the collection: "Mis à jour à …" shows it, in local time.

Every text a reader sees comes in both languages, as `{ "fr": "…", "en": "…" }`: `title`,
`severity_reason`, `lede`, `method`, `loot`, `am_i_affected`, `action`, each paragraph of
`summary`, each step of `protection_steps`, `attacker.name` and `attacker.country`,
`victim.label`, `timeline[].label` and `sources[].title`. A plain string counts for both
languages; when one language is missing, the other one is shown, since the information exists
and only its translation is missing. Codes (`severity`, `audience`, statuses, CVE numbers) are
the same in both languages.

| Field | Values | Shown (French page) |
|---|---|---|
| `id` | text | internal, stable |
| `severity` | `critique`, `grave`, `significative`, `mineure` | square and word, layout, tabs |
| `title` | 10 words at most in each language | card and panel |
| `lede` | one sentence | card; otherwise the first sentence of `summary` |
| `first_seen` | a day alone (`2026-11-18`) or a UTC time (`2026-11-18T07:42:00Z`) | "07 h 42", "aujourd'hui", "hier", "18 nov." |
| `audience` | `grand_public`, `entreprises`, `les_deux` | "Grand public uniquement", daily sentence |
| `exploited` | `true` only when a source confirms the flaw is already exploited | order of the cards |
| `reliability` | `confirme`, or anything else for a rumour | "Rumeur, non confirmée" |
| `reliability_source` | where a rumour was seen, e.g. `X` | "Rumeur vue sur X, non confirmée" |
| `attacker` | `name`, `country`, `status`, `source` | Origine |
| `victim` | `label` (45 characters at most in each language), `status` | Cibles |
| `method` | 45 characters at most in each language | Méthode |
| `loot` | 45 characters at most in each language | Impact |
| `am_i_affected` | one sentence, 75 characters at most in each language | "Suis-je concerné ?" |
| `action` | one sentence, 75 characters at most in each language | "Que faire :" |
| `severity_reason`, `summary`, `timeline`, `protection_steps`, `technical`, `sources` | as before | detail panel |
| `untranslated` | `["title"]`, or empty | the English page shows that title in French, marked `lang="fr"` |

The English page uses the same rules with the words of `src/lib/i18n.js`. `untranslated` marks a
title that the collector kept in French in the English version, because translating it would
have meant inventing (see the main README).

Statuses (`attacker.status`, `victim.status`): `confirme`, `revendique`, `presume`, `inconnu`.
A card shows a status only when it is not confirmed: "Revendiqué, non confirmé", "Présumé, non
confirmé". A ransomware claim comes with `reliability: "confirme"` (the claim was recorded) and
the `revendique` statuses (the attack is not confirmed).

The page is defensive about the feed:
- any missing information shows "Non communiqué" ("Not disclosed"), and its line stays;
- a day without a time is shown without a time, never as "01 h 00";
- a card without an explicit `reliability: "confirme"` is treated as a rumour;
- a claimed attack or a rumour is never shown above "Significative";
- an attacker name without a status is shown as "Présumé, non confirmé";
- links other than `http(s)`, and `.onion` addresses, are dropped;
- an entry without `id`, title, valid level or date is skipped.

## Layout of the code

```
src/
  config.js              APP_NAME
  main.jsx               entry point
  lang.jsx               the language: default, choice kept, <html lang>; useLang()
  index.css              tokens (colours, font, sizes), components
  App.jsx                the page: daily sentence, tabs, layout by severity, panels
  hooks.js               useAttacks (data/cards.json, read again every 5 min), localize, useNow, useStored
  lib/i18n.js            interface texts, in French and in English
  lib/digest.js          the daily sentence, counted on the cards shown
  lib/format.js          dates in both languages, search, Origine and Cibles, sources, safe links
  lib/severity.js        levels and squares, statuses, severity grid, claim rule, in both languages
  lib/typo.js            French typography, for French texts only
  components/
    Header.jsx           name, search, "Mis à jour à 15 h 30", FR | EN
    Filters.jsx          tabs with counts, "Grand public uniquement"
    AttackCard.jsx       headline card, card, "En bref" list
    Severity.jsx         10px square, first line of a card
    Drawer.jsx           detail panel: Escape, click outside, focus kept then given back
    AttackDrawer.jsx     "Lire la fiche"
    MethodDrawer.jsx     "Méthode et sources"
scripts/
  check.mjs              automated browser checks (Playwright)
  fixtures.mjs           test cards, used by check.mjs only
```

## Choices

### Layout: the size of the card tells the severity

- **Header**, one line: the name, the search (`/` or Ctrl+K), "Mis à jour à 15 h 30" in grey,
  the time of the last collection, and FR | EN.
- **Date, then one sentence** counted on the cards shown, for example "Depuis hier : 1 attaque
  critique et 2 graves. 2 concernent le grand public." The period says which cards are counted:
  "Aujourd'hui" when they are all from today, "Depuis hier" when some are from yesterday, "Ces
  sept derniers jours" when nothing happened since yesterday ("Today", "Since yesterday", "Over
  the last seven days" in English). It is never written in advance.
- **Tabs** with their counts, underlined when active; "Grand public uniquement" on the right.
  Without any card, neither tabs nor sentence: only "Aucune attaque recensée pour le moment".
- **Order**: the most serious first, then the newest day; on the same day and at the same level,
  a flaw already exploited (`exploited: true`) before one that is not, then the latest time. This
  holds for the headline, the columns and "En bref".
- **"Toutes"**: the headline (the most serious, then the most recent) across the full width,
  only if there is a critical or serious attack, so that a calm day looks calm. Then critical
  and serious attacks in 2 columns, significant ones in 3, minor ones in "En bref", one line
  each without a card. The other tabs show that level only, without a headline. On phones:
  one column, the headline first.

### The card

First line: the 10px square, the level in black, the short date in grey, and a status only if
it is not confirmed. Then the title, one sentence, Origine / Cibles / Méthode / Impact (grey
label, black value), "Suis-je concerné ?" on `#F3F3F3` with "Que faire :", and at the bottom
"Sources : …" with "Lire la fiche". No icon, no arrow, no uppercase label, no "·".

### Colours, and no other

Page `#F5F5F5`, cards `#FFFFFF`, border `#E2E2E2`, border on hover `#000000`. Titles `#000000`,
text `#333333`, secondary text `#666666`. Severity, like a weather warning, only on the
square: Mineure `#8A8A8A`, Significative `#F5C400` with a 1px `#8A6D00` outline, Grave
`#E8590C`, Critique `#C1121F`. No shadow, no gradient; 6px corners on cards, 0 elsewhere.

### Typography

One family, Inria Sans (300, 400, 700), self-hosted. Headline title 40px (22px on phones,
where 40px would take most of the screen), card titles 22px, text 16px, small text 14px. Line
height 1.5 for text and 1.15 for titles; 75 characters per line at most.

### Movement

Only the opening of the detail panel. No entrance animation. With reduced motion, the panel
appears without moving.

### Honesty and safety

The site shows real cards only and says how they are made: "Méthode et sources" lists the
sources the collector really reads, the severity grid includes the two criteria of phase 1
("une faille déjà exploitée dans un logiciel peu répandu", "une alerte du CERT-FR"), and the
footer says the cards are built by fixed rules, without AI. No request to another domain: fonts
are self-hosted, and built pages carry a Content-Security-Policy. No link to ransomware sites or
stolen data.

## Checks

`npm run check` builds the site into a temporary folder with the configuration of
`npm run build`, serves it, drives a browser with Playwright and prints one line per check. Test
pages run at a fixed moment, Friday 20 November 2026 at 15:00 in Paris. It covers:
- no test card and no "démo", "simulation", "fictif" or "fictional" in the code or the built site;
- both languages: every interface text in both dictionaries; the English page (tabs, daily
  sentence, "Updated at", cards, panel, "Method and sources") without French words or French
  typography, and the French page without English; FR | EN, kept after a reload; the default
  language taken from the browser; a stored value other than `fr` or `en` ignored; a title kept
  in French marked `lang="fr"`;
- the layout, from 360 to 1440px, the headline rule, columns and "En bref";
- the daily sentence, its updates (calm day, new critical attack, "Grand public uniquement")
  and its period ("Aujourd'hui", "Depuis hier", "Ces sept derniers jours");
- "Mis à jour à …" from `generated_at`, and the file read again every 5 minutes and when the
  tab comes back;
- days without a time, shown without a time;
- the page without file, with an empty file, with an HTML page instead, with a broken file;
- "Non communiqué", colours, shadows, gradients, corners, font, sizes and weights;
- the absence of animations, the panel, keyboard path and reduced motion;
- links, the Content-Security-Policy, and that no request goes to another domain;
- the real cards of `public/data/cards.json`, when the collector has written them.

It also saves screenshots in `captures/` (ignored by git), at 1440 and 390px wide, in French
(`-fr`) and in English (`-en`):
- `test-1440-fr.png`, `test-390-en.png`…: test cards, a usual day;
- `test-calme-…`: test cards, a calm day;
- `test-tiroir-…`: the detail panel open;
- `vide-…`: no file yet;
- `reel-…`: the real cards, when `public/data/cards.json` exists;
- `test-incomplet-1440.png`, `test-incomplet-390.png`: test cards missing information, in French.

The browser is Playwright's Chromium (once: `npx playwright install chromium`) or an
installed Chrome or Edge: `CHECK_BROWSER=chrome npm run check`.
