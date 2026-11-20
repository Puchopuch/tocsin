# Tocsin, frontend

A public information service, in French, about the cyberattacks that touch the general public
and businesses: calm and clear, neither a security dashboard nor a "hacker" look. It quotes
CERT-FR and other sources but must never look official (no Marianne font, no blue-white-red).

**Tocsin** is a provisional name. It lives in one constant, `APP_NAME` in `src/config.js`;
`vite.config.js` also writes it into the page title.

The site only reads `data/cards.json`, rebuilt every hour by a Python pipeline (not written
yet). It calls no API and holds no secret.

## Run it

Node.js 20.19 or newer.

```sh
npm ci               # install the pinned dependency tree
npm run dev          # http://localhost:5173, fictional demo data
npm run build        # the real site, in dist/
npm run build:demo   # one self-contained HTML file, in dist-demo/
npm run preview      # serves dist/ locally
npm run check        # automated browser checks and screenshots, see "Checks"
```

Dependencies are pinned to exact versions. Add one only with
`npm install --before=2026-11-05 --save-exact <package>`.

## Two modes

| | Demo | Real site |
|---|---|---|
| Commands | `npm run dev`, `npm run build:demo` | `npm run build` |
| Switch | `VITE_DEMO=true` (`.env.development`, `.env.demo`) | `VITE_DEMO` unset |
| Data | `src/data/demo.js`, fictional, dated from page load | `data/cards.json`, next to `index.html` |
| Under the header | "Données fictives", "Simuler une alerte", "Simuler une journée calme" | nothing |

If `data/cards.json` is missing or unreadable, the real site says so. It never falls back on
demo data.

## Data format: `data/cards.json`

```json
{ "generated_at": "2026-11-20T07:42:00Z", "attacks": [{ "id": "…" }] }
```

| Field | Values | Shown |
|---|---|---|
| `id` | text | internal, stable |
| `severity` | `critique`, `grave`, `significative`, `mineure` | square and word, layout, tabs |
| `title` | short, plain | card and panel |
| `lede` | one sentence | card; otherwise the first sentence of `summary` |
| `first_seen` | ISO date | "07 h 42", "hier", "18 nov." |
| `audience` | `grand_public`, `entreprises`, `les_deux` | "Grand public uniquement", daily sentence |
| `reliability` | `confirme`, or anything else for a rumour | "Rumeur, non confirmée" |
| `reliability_source` | where a rumour was seen, e.g. `X` | "Rumeur vue sur X, non confirmée" |
| `attacker` | `name`, `country`, `status`, `source` | Origine |
| `victim` | `label`, `status` | Cibles |
| `method` | short | Méthode |
| `loot` | short | Impact |
| `am_i_affected` | one sentence | "Suis-je concerné ?" |
| `action` | one sentence | "Que faire :" |
| `severity_reason`, `summary`, `timeline`, `protection_steps`, `technical`, `sources` | as before | detail panel |

Statuses (`attacker.status`, `victim.status`): `confirme`, `revendique`, `presume`, `inconnu`.
A card shows a status only when it is not confirmed: "Revendiqué, non confirmé", "Présumé, non
confirmé".

The page is defensive about the feed:
- any missing information shows "Non communiqué", and its line stays;
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
  index.css              tokens (colours, font, sizes), components
  App.jsx                the page: daily sentence, tabs, layout by severity, panels
  hooks.js               useAttacks (demo or data/cards.json), useNow, useStored (localStorage)
  data/demo.js           8 fictional attacks, a calm day, 3 simulated critical alerts
  lib/digest.js          the daily sentence, counted on the cards shown
  lib/format.js          French dates, search, Origine and Cibles, sources, safe links
  lib/severity.js        levels and squares, statuses, severity grid, claim rule
  lib/typo.js            French typography
  components/
    Header.jsx           name, search, "Mis à jour à 7 h 42", demo line
    Filters.jsx          tabs with counts, "Grand public uniquement"
    AttackCard.jsx       headline card, card, "En bref" list
    Severity.jsx         10px square, first line of a card
    Drawer.jsx           detail panel: Escape, click outside, focus kept then given back
    AttackDrawer.jsx     "Lire la fiche"
    MethodDrawer.jsx     "Méthode et sources"
scripts/check.mjs        automated browser checks (Playwright)
```

## Choices

### Layout: the size of the card tells the severity

- **Header**, one line: the name, the search (`/` or Ctrl+K), "Mis à jour à 7 h 42" in grey.
  In demo mode, a line "Données fictives" with the two simulations as small text links.
- **Date, then one sentence** counted on the cards shown, for example "Depuis hier : 1 attaque
  critique et 2 graves. 2 concernent le grand public." It covers yesterday and today, or the
  last seven days when nothing happened since yesterday. It is never written in advance.
- **Tabs** with their counts, underlined when active; "Grand public uniquement" on the right.
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

The demo is fictional and says so. No request to another domain: fonts are self-hosted, and
built pages carry a Content-Security-Policy. No link to ransomware sites or stolen data.

## Checks

`npm run check` starts the dev server and a build of the real site, drives a browser with
Playwright and prints one line per check. It covers:
- the layout, from 360 to 1440px;
- the headline rule, columns and "En bref";
- the daily sentence and its updates after the calm day and the simulated alert, and that no
  sentence is written in the code;
- "Non communiqué";
- colours, shadows, gradients, corners, font, sizes and weights;
- the absence of animations;
- the panel, keyboard path and reduced motion;
- the real site without data and with a test feed missing information;
- links, the Content-Security-Policy, and that no request goes to another domain.

It also saves screenshots in `captures/` (ignored by git):
- `demo-1440.png`, `demo-390.png`: the usual day;
- `demo-calme-1440.png`, `demo-calme-390.png`: the calm day;
- `demo-tiroir-1440.png`, `demo-tiroir-390.png`: the detail panel open;
- `reel-test-1440.png`, `reel-test-390.png`: the real site with a test feed where some cards
  miss information.

`npm run dev:real` does not exist yet: there are no real cards until the pipeline is written.

The browser is Playwright's Chromium (once: `npx playwright install chromium`) or an
installed Chrome or Edge: `CHECK_BROWSER=chrome npm run check`.
