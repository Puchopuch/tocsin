// Automated browser checks of the frontend, run with `npm run check`.
//
// The site has one mode: it shows the cards of data/cards.json, written by the collector. The
// check builds it into a temporary folder with the configuration of `npm run build`, verifies that
// nothing fictional reached the build, then serves it and drives a browser with Playwright. The
// test cards (scripts/fixtures.mjs) reach the page only by intercepting its request for
// data/cards.json: no test file is ever written into the site. Each test page runs at a fixed
// moment, Friday 20 November 2026 at 15:00 in Paris. One line per check; screenshots in
// captures/ (ignored by git), including the real cards when public/data/cards.json exists.
//
// Browser: Playwright's own Chromium (`npx playwright install chromium`, once), or a Chrome or
// Edge already installed: CHECK_BROWSER=chrome npm run check (or msedge).

import { existsSync } from 'node:fs';
import { mkdir, readdir, readFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { build, createServer, preview } from 'vite';
import { APP_NAME } from '../src/config.js';
import { safeUrl } from '../src/lib/format.js';
import { LANG_KEY, UI } from '../src/lib/i18n.js';
import { CLAIM_RULE, GRID, GRID_INTRO, LEVEL_NAMES, STATUS } from '../src/lib/severity.js';
import { buildAlert, buildFeed, INVENTED_NAMES } from './fixtures.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const captures = path.join(root, 'captures');
const out = path.join(os.tmpdir(), 'tocsin-check-dist');
const realFile = path.join(root, 'public', 'data', 'cards.json');
const WIDTHS = [360, 390, 768, 1024, 1440];

const NOW = Date.parse('2026-11-20T14:00:00Z');
const HOUR = 3_600_000;
const DAY = 24 * HOUR;

// Test feeds, all dated from NOW.
const usual = buildFeed(NOW);
const calm = buildFeed(NOW, { calm: true });
const alertDay = { ...usual, attacks: [buildAlert(0, NOW), ...usual.attacks] };
const todayOnly = { ...usual, attacks: usual.attacks.filter((a) => NOW - Date.parse(a.first_seen) < 6 * HOUR) };
const lastWeek = {
  ...usual,
  attacks: usual.attacks.map((a) => ({ ...a, first_seen: new Date(Date.parse(a.first_seen) - 3 * DAY).toISOString() })),
};
const emptyFeed = { generated_at: new Date(NOW - 10 * 60_000).toISOString(), attacks: [] };
const vendalo = usual.attacks.find((a) => a.id === 'test-vendalo');
const dayOnlyCard = (id, day) => ({
  ...structuredClone(vendalo),
  id,
  first_seen: day,
  timeline: [
    { date: day, label: 'Ajout à une liste officielle' },
    { date: '2026-12-04', label: 'Date limite de correction' },
  ],
});
const dayOnly = { generated_at: usual.generated_at, attacks: [dayOnlyCard('test-jour', '2026-11-20'), dayOnlyCard('test-veille', '2026-11-19')] };
// Same level and same day: the card of a flaw already exploited comes first, wherever it stands.
const amperys = usual.attacks.find((a) => a.id === 'test-amperys');
const tieCard = (id, title, base, severity, day, exploited) => ({ ...structuredClone(base), id, title, severity, first_seen: day, exploited });
const tie = {
  generated_at: usual.generated_at,
  attacks: [
    tieCard('test-alerte', 'Alerte sans exploitation connue', amperys, 'grave', '2026-11-20', false),
    tieCard('test-exploitee', 'Faille déjà exploitée', amperys, 'grave', '2026-11-20', true),
    tieCard('test-hier', 'Faille exploitée hier', amperys, 'grave', '2026-11-19', true),
    tieCard('test-sig-alerte', 'Significative sans exploitation', vendalo, 'significative', '2026-11-20', false),
    tieCard('test-sig-exploitee', 'Significative déjà exploitée', vendalo, 'significative', '2026-11-20', true),
  ],
};

// The only colours allowed by the design brief, as the browser reports them.
const COLOURS = new Set([
  'rgb(245, 245, 245)', // page
  'rgb(255, 255, 255)', // cards
  'rgb(226, 226, 226)', // borders
  'rgb(0, 0, 0)', // titles, hover border
  'rgb(51, 51, 51)', // text
  'rgb(102, 102, 102)', // secondary text
  'rgb(243, 243, 243)', // "Suis-je concerné ?"
  'rgb(138, 138, 138)', // mineure
  'rgb(245, 196, 0)', // significative
  'rgb(138, 109, 0)', // significative outline
  'rgb(232, 89, 12)', // grave
  'rgb(193, 18, 31)', // critique
  'rgba(0, 0, 0, 0)', // transparent
]);

// Words that must never be seen on the site: it shows real cards only.
const FICTION = /\bd[ée]mo\b|\bsimul(?:ation|ations|er|ée|ées)\b|\bfictif|\bfictive|\bfictional\b|données fictives/i;

// Words of the interface that must never show in the other language.
const FRENCH_UI = /Mis à jour|Lire la fiche|Suis-je concerné|Que faire|\bOrigine\b|\bCibles\b|\bToutes\b|Grand public uniquement|Non communiqué|En bref|\bFermer\b|Chronologie|\bSignificative\b|\bMineure\b|Depuis hier|Aujourd’hui/;
const ENGLISH_UI = /\bUpdated\b|Read more|Am I affected|What to do|\bOrigin\b|\bTargets\b|General public only|Not disclosed|In brief|\bClose\b|\bTimeline\b|Since yesterday|\bSevere\b|\bSignificant\b/;

const results = [];
function report(label, ok, detail = '') {
  results.push(ok);
  console.log(`${ok ? 'OK  ' : 'FAIL'}  ${label}${detail ? `  (${detail})` : ''}`);
}

const clean = (text) => (text ?? '').replace(/\s+/g, ' ').trim();
const CARDS = '#attaques article, .brief__row';

async function filesIn(dir) {
  const entries = await readdir(dir, { recursive: true, withFileTypes: true });
  return entries.filter((entry) => entry.isFile()).map((entry) => path.join(entry.parentPath ?? entry.path, entry.name));
}

/** Waits, from Node, until the predicate holds in the page (works with a fake clock too). */
async function until(page, predicate, arg, timeout = 8000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    if (await page.evaluate(predicate, arg)) return true;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return false;
}

// ---------------------------------------------------------------------------------------------
// The code and the build

await rm(captures, { recursive: true, force: true });
await mkdir(captures, { recursive: true });

{
  const files = (await filesIn(path.join(root, 'src'))).filter((file) => /\.(js|jsx)$/.test(file));
  const written = [];
  const invented = [];
  for (const file of files) {
    const source = await readFile(file, 'utf8');
    const name = path.relative(root, file);
    if (/(Depuis hier|Aujourd’hui|Ces sept derniers jours)\s*:\s*\d|\d+ attaques? (critiques?|graves?|significatives?|mineures?)/.test(source)) written.push(name);
    if (/(Since yesterday|Today|Over the last seven days):\s*\d|\d+ (critical|severe|significant|minor)( and \d+ \w+)? attacks?\b/.test(source)) written.push(name);
    if (INVENTED_NAMES.some((invention) => source.includes(invention)) || /fixtures/.test(source)) invented.push(name);
  }
  report('La phrase du jour n’est écrite nulle part dans le code', written.length === 0, written.join(', '));
  report('Aucune donnée de test dans src/ : elles vivent dans scripts/fixtures.mjs', invented.length === 0, invented.join(', '));
}

// Security of the code: no HTML or script sink, and nothing read from the address, the referrer
// or other windows, which could change what the page shows or where it reads its data.
{
  const SINKS = /dangerouslySetInnerHTML|\.(?:inner|outer)HTML\b|insertAdjacentHTML|document\.write|\beval\s*\(|\bnew\s+Function\b|\bFunction\s*\(|set(?:Timeout|Interval)\s*\(\s*['"`]|createContextualFragment|\bsrcdoc\b|parseFromString/;
  const INPUTS = /\blocation\b|URLSearchParams|document\.referrer|window\.name|\bpostMessage\b|addEventListener\(\s*['"]message['"]/;
  const sinks = [];
  const inputs = [];
  for (const file of (await filesIn(path.join(root, 'src'))).filter((name) => /\.(js|jsx)$/.test(name))) {
    (await readFile(file, 'utf8')).split('\n').forEach((line, index) => {
      const where = `${path.relative(root, file)}:${index + 1}`;
      if (SINKS.test(line)) sinks.push(where);
      if (INPUTS.test(line)) inputs.push(where);
    });
  }
  report('Code du site : ni dangerouslySetInnerHTML, innerHTML, document.write, eval ni new Function', sinks.length === 0, sinks.join(', '));
  report('Code du site : rien n’est lu dans l’adresse, le référent ou d’autres fenêtres', inputs.length === 0, inputs.join(', '));
}

// The site checks every link again, with the rules and the cases of the collector.
{
  const cases = JSON.parse(await readFile(path.join(root, '..', 'collector', 'tests', 'data', 'links.json'), 'utf8'));
  const wrong = [...cases.refused.filter((url) => safeUrl(url) !== null), ...cases.accepted.filter((url) => safeUrl(url) === null)];
  report(
    `Liens revérifiés par le site : ${cases.refused.length} liens dangereux refusés (javascript:, data:, vbscript:, file:, //, identifiants, .onion, xn--, IP, majuscules, encodage, espaces), ${cases.accepted.length} liens https ordinaires gardés`,
    wrong.length === 0,
    wrong.map((url) => JSON.stringify(url)).join(' | '),
  );
}

// Every text of the interface exists in both languages, with the same shape.
{
  const problems = [];
  const compare = (fr, en, where) => {
    for (const key of new Set([...Object.keys(fr ?? {}), ...Object.keys(en ?? {})])) {
      const a = fr?.[key];
      const b = en?.[key];
      const at = `${where}.${key}`;
      if (a === undefined || b === undefined) problems.push(`${at} manque en ${a === undefined ? 'français' : 'anglais'}`);
      else if (typeof a !== typeof b || Array.isArray(a) !== Array.isArray(b)) problems.push(`${at} n’a pas la même forme`);
      else if (Array.isArray(a)) {
        if (a.length !== b.length) problems.push(`${at} n’a pas autant d’éléments`);
        a.forEach((item, index) => compare([item].flat(), [b[index]].flat(), `${at}[${index}]`));
      } else if (typeof a === 'object' && a !== null) compare(a, b, at);
      else if (typeof a === 'string' && (!a.trim() || !b.trim())) problems.push(`${at} est vide`);
    }
  };
  compare(UI.fr, UI.en, 'UI');
  compare(LEVEL_NAMES.fr, LEVEL_NAMES.en, 'LEVEL_NAMES');
  for (const [key, status] of Object.entries(STATUS)) compare(status.fr, status.en, `STATUS.${key}`);
  compare(GRID.fr, GRID.en, 'GRID');
  compare({ text: GRID_INTRO.fr }, { text: GRID_INTRO.en }, 'GRID_INTRO');
  compare({ text: CLAIM_RULE.fr }, { text: CLAIM_RULE.en }, 'CLAIM_RULE');
  report('Chaque texte de l’interface existe en français et en anglais, sans trou', problems.length === 0, problems.slice(0, 6).join(' | '));
}

await build({ root, logLevel: 'error', build: { outDir: out, emptyOutDir: true } });

{
  const found = [];
  for (const file of await filesIn(out)) {
    if (/\.(woff2?|png|jpe?g|ico|svg)$/.test(file)) continue;
    const text = await readFile(file, 'utf8');
    const name = path.relative(out, file);
    for (const invention of INVENTED_NAMES) if (text.includes(invention)) found.push(`${name} : ${invention}`);
    // data/cards.json holds real cards, whose words are not ours: only invented names count there.
    const word = name.startsWith('data') ? null : FICTION.exec(text);
    if (word) found.push(`${name} : « ${word[0]} »`);
  }
  report('Le site construit ne contient aucune donnée de test, ni « démo », « simulation » ou « fictif »', found.length === 0, found.slice(0, 6).join(' | '));
}

// The build holds the site and nothing else, and its page carries the strict CSP.
{
  const ALLOWED = [
    /^index\.html$/,
    /^assets\/index-[\w-]+\.(?:js|css)$/,
    /^assets\/inria-sans-latin-(?:300|400|700)-normal-[\w-]+\.woff2$/,
    /^data\/cards\.json$/,
  ];
  const names = (await filesIn(out)).map((file) => path.relative(out, file).split(path.sep).join('/'));
  const unexpected = names.filter((name) => !ALLOWED.some((pattern) => pattern.test(name)));
  report('Build : seulement la page, ses scripts, styles et polices, et data/cards.json', unexpected.length === 0 && names.includes('index.html'), unexpected.join(', ') || `${names.length} fichiers`);

  const SECRETS = /RANSOMWARE_LIVE_API_KEY|MISTRAL_API_KEY|X-API-KEY|api-pro\.ransomware\.live|state\.db|collector\.log|fixtures\.mjs|PRIVATE KEY/;
  const leaks = [];
  for (const file of await filesIn(out)) {
    if (file.endsWith('.woff2')) continue;
    const found = SECRETS.exec(await readFile(file, 'utf8'));
    if (found) leaks.push(`${path.relative(out, file)} : ${found[0]}`);
  }
  report('Build : aucune clé ni nom de clé, aucune trace de .env, state.db, journal ou données de test', leaks.length === 0, leaks.join(' | '));

  const html = await readFile(path.join(out, 'index.html'), 'utf8');
  const scripts = html.match(/<script\b[^>]*>/g) ?? [];
  const handlers = html.match(/\son[a-z]+\s*=/gi) ?? [];
  report('index.html construit : un seul script, chargé depuis le site, aucun script en ligne ni attribut on…=', scripts.length === 1 && /\bsrc="\.\/assets\//.test(scripts[0]) && handlers.length === 0, scripts.join(' '));

  const policy = /<meta http-equiv="Content-Security-Policy" content="([^"]+)"/.exec(html)?.[1] ?? '';
  const directives = Object.fromEntries(
    policy
      .split(';')
      .map((part) => part.trim().split(/\s+/))
      .filter((words) => words[0])
      .map(([name, ...values]) => [name, values.join(' ')]),
  );
  const EXPECTED = {
    'default-src': "'self'",
    'script-src': "'self'",
    'connect-src': "'self'",
    'object-src': "'none'",
    'base-uri': "'none'",
    'form-action': "'none'",
    'require-trusted-types-for': "'script'",
    'trusted-types': "'none'",
  };
  const wrong = Object.entries(EXPECTED)
    .filter(([name, value]) => directives[name] !== value)
    .map(([name]) => `${name} = ${directives[name] ?? 'absente'}`);
  report(
    'CSP du build : script-src \'self\' sans unsafe-inline ni unsafe-eval ; object-src, base-uri, form-action \'none\' ; connect-src \'self\' ; Trusted Types exigés',
    wrong.length === 0,
    wrong.join(' | ') || policy,
  );
}

const previewServer = await preview({ root, logLevel: 'error', build: { outDir: out }, preview: { port: 4199, strictPort: false } });
const base = previewServer.resolvedUrls.local[0];
const browser = await chromium.launch({ channel: process.env.CHECK_BROWSER || undefined });
const offsite = [];
const violations = [];
const dialogs = [];

// The dev and preview servers answer this computer only, never the local network.
{
  const dev = await createServer({ root, logLevel: 'error', server: { port: 5199, strictPort: false } });
  await dev.listen();
  const devAddress = dev.httpServer.address();
  await dev.close();
  const previewAddress = previewServer.httpServer.address();
  report(
    'Serveurs de développement et de prévisualisation : 127.0.0.1 seulement',
    devAddress.address === '127.0.0.1' && previewAddress.address === '127.0.0.1',
    `${devAddress.address}:${devAddress.port} ; ${previewAddress.address}:${previewAddress.port}`,
  );
}

/**
 * A page of the built site. `feed` stands for data/cards.json: an object, an HTTP status, raw
 * text, a function returning one of these at each request, or null for the real file. `timers`:
 * "fixed" (the date is NOW), "fake" (NOW, and time moves only when the test says so) or "real".
 */
async function openPage({ feed = usual, width = 1440, height = 900, reduce = false, waitFor = CARDS, timers = 'fixed', locale = 'fr-FR', stored, address = '', seenViolations = violations } = {}) {
  const context = await browser.newContext({
    viewport: { width, height },
    reducedMotion: reduce ? 'reduce' : 'no-preference',
    locale,
    timezoneId: 'Europe/Paris',
  });
  // Every page reports the CSP and Trusted Types violations it meets.
  await context.addInitScript(() => {
    document.addEventListener('securitypolicyviolation', (event) => console.error(`CSP violation: ${event.violatedDirective} ${event.blockedURI}`));
  });
  if (stored !== undefined) {
    await context.addInitScript(([key, value]) => window.localStorage.setItem(key, value), [LANG_KEY, stored]);
  }
  const page = await context.newPage();
  const errors = [];
  const requests = { feed: 0, urls: [] };
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (!['data:', 'blob:'].includes(url.protocol) && url.origin !== new URL(base).origin) offsite.push(url.href);
  });
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
    if (/Content.Security.Policy|CSP violation|Trusted ?Type/i.test(message.text())) seenViolations.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(String(error)));
  page.on('dialog', (dialog) => {
    dialogs.push(dialog.message());
    dialog.dismiss().catch(() => {});
  });
  await page.route('**/data/cards.json', (route) => {
    requests.feed += 1;
    requests.urls.push(route.request().url());
    const current = typeof feed === 'function' ? feed() : feed;
    if (current === null) return route.continue();
    if (typeof current === 'number') return route.fulfill({ status: current, contentType: 'text/plain', body: 'Not found' });
    if (typeof current === 'string') {
      return route.fulfill({ status: 200, contentType: current.startsWith('<') ? 'text/html' : 'application/json', body: current });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(current) });
  });
  if (timers === 'fixed') await page.clock.setFixedTime(NOW);
  if (timers === 'fake') await page.clock.install({ time: NOW });
  await page.goto(base + address);
  if (waitFor) await page.waitForSelector(waitFor);
  await page.evaluate(() => document.fonts.ready);
  return { context, page, errors, requests };
}

const tabTexts = (page) => page.$$eval('.tab', (tabs) => tabs.map((tab) => tab.textContent.replace(/\s+/g, ' ').trim()));
const digestText = (page) => page.locator('.digest__text').textContent().then(clean);
const updatedText = (page) => page.locator('.site-header__updated').textContent().then(clean);
const layout = (page) =>
  page.evaluate(() => ({
    une: document.querySelector('.une .une__title')?.textContent ?? null,
    two: document.querySelectorAll('.grid-cards--2 > .card').length,
    three: document.querySelectorAll('.grid-cards--3 > .card').length,
    brief: document.querySelectorAll('.brief__row').length,
    briefHeading: document.querySelector('#en-bref') !== null,
  }));

/** Every rule of the design brief that can be read on the page itself. */
async function styleAudit(page) {
  return page.evaluate((allowed) => {
    const problems = new Set();
    const sizes = new Set();
    const weights = new Set();
    for (const el of document.querySelectorAll('body *')) {
      if (el.closest('[aria-hidden="true"]') && !el.classList.contains('square')) continue;
      const s = getComputedStyle(el);
      const colours = [s.color, s.backgroundColor];
      for (const side of ['Top', 'Right', 'Bottom', 'Left']) {
        if (parseFloat(s[`border${side}Width`]) > 0) colours.push(s[`border${side}Color`]);
      }
      for (const colour of colours) if (!allowed.includes(colour)) problems.add(`couleur ${colour} (${el.className || el.tagName})`);
      if (s.boxShadow !== 'none') problems.add(`ombre sur ${el.className || el.tagName}`);
      if (s.textShadow !== 'none') problems.add(`ombre de texte sur ${el.className || el.tagName}`);
      if (s.backgroundImage !== 'none') problems.add(`dégradé ou image sur ${el.className || el.tagName}`);
      if (s.textTransform !== 'none') problems.add(`majuscules forcées sur ${el.className || el.tagName}`);
      const radius = s.borderTopLeftRadius;
      const isCard = el.classList.contains('card') || el.classList.contains('une');
      if ((isCard && radius !== '6px') || (!isCard && radius !== '0px' && el.type !== 'checkbox')) problems.add(`arrondi ${radius} sur ${el.className || el.tagName}`);
      if (!s.fontFamily.startsWith('"Inria Sans"')) problems.add(`police ${s.fontFamily}`);
      const ownText = [...el.childNodes].some((node) => node.nodeType === 3 && node.textContent.trim());
      if (ownText && el.getClientRects().length > 0 && !el.closest('.sr-only')) {
        sizes.add(s.fontSize);
        weights.add(s.fontWeight);
      }
    }
    return { problems: [...problems], sizes: [...sizes].sort(), weights: [...weights].sort() };
  }, [...COLOURS]);
}

try {
  // Screenshots in French and in English: the usual day, a calm day and the detail panel, with
  // test cards.
  {
    const shoot = async (name, { feed = usual, width, height, act, full = true, locale }) => {
      const { context, page } = await openPage({ feed, width, height, locale });
      if (act) await act(page);
      await page.waitForTimeout(400);
      await page.screenshot({ path: path.join(captures, name), fullPage: full });
      await context.close();
    };
    const sheet = async (page) => {
      await page.locator('.une .card__foot .link').click();
      await page.waitForSelector('[role="dialog"]');
      await page.waitForTimeout(600); // let the panel finish sliding in
    };
    for (const [lang, locale] of [
      ['fr', 'fr-FR'],
      ['en', 'en-GB'],
    ]) {
      for (const [width, height] of [
        [1440, 900],
        [390, 844],
      ]) {
        await shoot(`test-${width}-${lang}.png`, { width, height, locale });
        await shoot(`test-calme-${width}-${lang}.png`, { feed: calm, width, height, locale });
        await shoot(`test-tiroir-${width}-${lang}.png`, { width, height, locale, act: sheet, full: false });
      }
    }
  }

  // English: every text of the interface and of the cards in English, nothing left in French.
  {
    const { context, page, errors } = await openPage({ locale: 'en-GB' });
    const state = await page.evaluate(() => ({ lang: document.documentElement.lang, title: document.title }));
    const tabs = await tabTexts(page);
    const text = await page.evaluate(() => document.body.innerText);
    const une = clean(await page.locator('.une .une__title').textContent());
    report('Anglais : <html lang="en">, titre de page et onglets Critical, Severe, Significant, Minor', state.lang === 'en' && state.title === `${APP_NAME}, today’s cyberattacks` && JSON.stringify(tabs) === JSON.stringify(['All 8', 'Critical 1', 'Severe 2', 'Significant 3', 'Minor 2']), `${state.lang} ; ${state.title} ; ${tabs.join(', ')}`);
    report('Anglais : phrase du jour et « Updated at » de la collecte', (await digestText(page)) === 'Since yesterday: 1 critical and 2 severe alerts. 2 affect the general public.' && (await updatedText(page)) === 'Updated at 14:48', `${await digestText(page)} ; ${await updatedText(page)}`);
    report('Anglais : les cartes parlent anglais', une === 'Massive data leak at the operator TelecomX' && /Am I affected\?/.test(text) && /What to do:/.test(text) && /Not disclosed/.test(text), une);
    report('Anglais : aucun texte de l’interface en français', !FRENCH_UI.test(text), FRENCH_UI.exec(text)?.[0] ?? '');
    report('Typographie française seulement en français : aucune espace insécable avant « : ; ? ! » en anglais', !/[  ][:;?!»]/.test(text) && !/«/.test(text));

    await page.locator('.une .card__foot .link').click();
    await page.waitForSelector('[role="dialog"]');
    const sheetText = await page.locator('[role="dialog"]').innerText();
    await page.keyboard.press('Escape');
    await page.waitForSelector('[role="dialog"]', { state: 'detached' });
    await page.click('text=Method and sources');
    await page.waitForSelector('[role="dialog"]');
    const methodText = await page.locator('[role="dialog"]').innerText();
    await context.close();
    report(
      'Anglais : fiche et « Method and sources » traduites',
      ['Close', 'What happened', 'Timeline', 'Technical details', 'Sources', 'Detected on'].every((part) => sheetText.includes(part)) &&
        ['Severity', 'or a CERT-FR alert', 'less common software', 'Claimed, not confirmed', 'Where the information comes from'].every((part) => methodText.includes(part)) &&
        !FRENCH_UI.test(sheetText + methodText),
      FRENCH_UI.exec(sheetText + methodText)?.[0] ?? '',
    );
    report('Anglais : aucune erreur dans la console', errors.length === 0, errors.join(' | '));
  }

  // The language: the browser's by default, then the reader's choice, kept in this browser only.
  {
    const french = await openPage();
    const frenchText = await french.page.evaluate(() => document.body.innerText);
    report('Français : aucun texte de l’interface en anglais, et la typographie française', !ENGLISH_UI.test(frenchText) && / :/.test(frenchText), ENGLISH_UI.exec(frenchText)?.[0] ?? '');
    await french.page.click('.lang-switch button[lang="en"]');
    const switched = await french.page.evaluate(() => ({ lang: document.documentElement.lang, tab: document.querySelector('.tab')?.textContent.trim() }));
    await french.page.reload();
    await french.page.waitForSelector(CARDS);
    const kept = await french.page.evaluate((key) => ({ lang: document.documentElement.lang, stored: window.localStorage.getItem(key) }), LANG_KEY);
    await french.context.close();
    report('Bouton FR | EN : la page passe en anglais, le choix est gardé après rechargement', switched.lang === 'en' && switched.tab.startsWith('All') && kept.lang === 'en' && kept.stored === 'en', JSON.stringify({ switched, kept }));

    const german = await openPage({ locale: 'de-DE' });
    const germanLang = await german.page.evaluate(() => document.documentElement.lang);
    await german.context.close();
    const forged = await openPage({ stored: '<img src=x onerror=alert(1)>' });
    const forgedLang = await forged.page.evaluate(() => document.documentElement.lang);
    await forged.context.close();
    report('Langue par défaut : celle du navigateur (anglais si ni français ni anglais) ; le stockage n’accepte que « fr » ou « en »', germanLang === 'en' && forgedLang === 'fr', `${germanLang} ; ${forgedLang}`);
  }

  // Widths: no sideways scroll, one-line header, one column on phones with the headline first.
  {
    const problems = [];
    for (const width of WIDTHS) {
      const { context, page } = await openPage({ width, height: 900 });
      const m = await page.evaluate(() => {
        const rect = (el) => el.getBoundingClientRect();
        const middle = (el) => rect(el).top + rect(el).height / 2;
        const name = document.querySelector('.site-header__name');
        const search = document.querySelector('.site-header__search');
        const updated = document.querySelector('.site-header__updated');
        const articles = [...document.querySelectorAll('#attaques article')];
        return {
          docWidth: document.documentElement.scrollWidth,
          oneLine: Math.abs(middle(name) - middle(search)) < 3 && Math.abs(middle(name) - middle(updated)) < 3,
          firstIsUne: articles[0]?.classList.contains('une') ?? false,
          lefts: new Set(articles.map((a) => Math.round(rect(a).left))).size,
        };
      });
      if (m.docWidth > width) problems.push(`${width}px : défilement (${m.docWidth})`);
      if (width >= 768 && !m.oneLine) problems.push(`${width}px : en-tête sur plusieurs lignes`);
      if (!m.firstIsUne) problems.push(`${width}px : la une n'est pas en premier`);
      if (width < 768 && m.lefts !== 1) problems.push(`${width}px : plus d'une colonne`);
      await context.close();
    }
    report('Largeurs 360 à 1440 px : pas de défilement, en-tête d’une ligne, mobile en une colonne, la une d’abord', problems.length === 0, problems.join('; '));
  }

  // The usual day: layout, sentence, time of the collection, style.
  {
    const { context, page, errors } = await openPage();
    const tabs = await tabTexts(page);
    report('Onglets : Toutes 8, Critique 1, Grave 2, Significative 3, Mineure 2', JSON.stringify(tabs) === JSON.stringify(['Toutes 8', 'Critique 1', 'Grave 2', 'Significative 3', 'Mineure 2']), tabs.join(', '));
    report('Phrase calculée sur les cartes', (await digestText(page)) === 'Depuis hier : 1 alerte critique et 2 graves. 2 concernent le grand public.', await digestText(page));
    const stamp = await page.locator('.site-header__updated time').getAttribute('datetime');
    report('« Mis à jour à … » : l’heure de la collecte inscrite dans le fichier', (await updatedText(page)) === 'Mis à jour à 14 h 48' && stamp === usual.generated_at, `${await updatedText(page)} ; ${stamp}`);
    const l = await layout(page);
    report('À la une : la critique ; graves sur 2 colonnes, significatives sur 3, mineures « En bref »', l.une?.includes('TelecomX') && l.two === 2 && l.three === 3 && l.brief === 2 && l.briefHeading, JSON.stringify(l));
    const grid = await page.evaluate(() => {
      const columns = (selector) => getComputedStyle(document.querySelector(selector)).gridTemplateColumns.split(' ').length;
      return { two: columns('.grid-cards--2'), three: columns('.grid-cards--3') };
    });
    report('Grilles à 1440 px : 2 et 3 colonnes', grid.two === 2 && grid.three === 3, JSON.stringify(grid));

    const typo = await page.evaluate(() => {
      const css = (selector) => getComputedStyle(document.querySelector(selector));
      return {
        une: css('.une__title').fontSize,
        card: css('.card__title').fontSize,
        text: css('.card__lede').fontSize,
        textLine: css('.card__lede').lineHeight,
        titleLine: css('.card__title').lineHeight,
        measure: css('.card__lede').maxWidth,
      };
    });
    report(
      'Typo : une 40 px, cartes 22 px, texte 16 px, interlignes 1,5 et 1,15, 75 caractères au plus',
      typo.une === '40px' && typo.card === '22px' && typo.text === '16px' && typo.textLine === '24px' && Math.abs(parseFloat(typo.titleLine) - 25.3) < 0.1 && typo.measure !== 'none',
      JSON.stringify(typo),
    );

    const audit = await styleAudit(page);
    report('Seules les couleurs du brief ; ni ombre, ni dégradé, ni majuscules ; arrondi 6 px sur les cartes, 0 ailleurs ; Inria Sans seule', audit.problems.length === 0, audit.problems.slice(0, 6).join(' | '));
    report('Tailles 14, 16, 22 et 40 px ; graisses 300, 400 et 700', audit.sizes.every((s) => ['14px', '16px', '22px', '40px'].includes(s)) && audit.weights.every((w) => ['300', '400', '700'].includes(w)), `${audit.sizes.join(' ')} / ${audit.weights.join(' ')}`);

    const text = await page.evaluate(() => document.body.innerText);
    report('Pas de « · », de flèche, de badge « Confirmé » ni d’« En direct »', !/[·→]/.test(text) && !/\bConfirmé\b/.test(text) && !/en direct/i.test(text));
    report('Statut seulement quand il n’est pas confirmé', /Revendiqué, non confirmé/.test(text) && /Présumé, non confirmé/.test(text) && /Rumeur vue sur X, non confirmée/.test(text));
    report('Information absente : « Non communiqué », la ligne reste', (text.match(/Non communiqué/g) ?? []).length >= 3);
    report(`Nom tiré de APP_NAME (« ${APP_NAME} ») dans l’en-tête et le titre de page`, clean(await page.locator('.site-header__name').textContent()) === APP_NAME && (await page.title()).startsWith(APP_NAME));
    report('Plus de ligne de démo ni de lien de simulation', (await page.locator('.demo-line').count()) === 0 && !/Simuler|Données fictives/.test(text));
    report('Pied de page : les fiches sont construites sans IA, sans le prétendre', /par des règles fixes, sans IA/.test(text) && !/rédigées par une IA/.test(text));
    report('Aucune animation au chargement', (await page.evaluate(() => document.getAnimations().length)) === 0);
    report('Aucune erreur dans la console', errors.length === 0, errors.join(' | '));

    await page.click('.tab:has-text("Critique")');
    const critique = await layout(page);
    await page.click('.tab:has-text("Mineure")');
    const mineure = await layout(page);
    await page.click('.tab:has-text("Toutes")');
    report('Autres onglets : ce niveau seulement, sans une', critique.une === null && critique.two === 1 && critique.three === 0 && mineure.une === null && mineure.brief === 2 && mineure.two + mineure.three === 0);

    await page.check('.public-only input');
    const publicTabs = await tabTexts(page);
    const publicDigest = await digestText(page);
    await page.uncheck('.public-only input');
    // Without the two business cards of yesterday, every card counted is from today.
    report('« Grand public uniquement » : les attaques d’entreprises disparaissent, la phrase et sa période suivent', publicTabs[0] === 'Toutes 6' && publicDigest === 'Aujourd’hui : 1 attaque critique et 1 grave. 2 concernent le grand public.', `${publicTabs[0]} ; ${publicDigest}`);

    await page.keyboard.press('/');
    const slash = await page.evaluate(() => document.activeElement?.id === 'search');
    await page.keyboard.type('telecomx');
    const searched = await layout(page);
    await page.keyboard.press('Escape');
    report('Recherche instantanée, « / » pour y aller, Échap pour effacer', slash && searched.une?.includes('TelecomX') && searched.two + searched.three + searched.brief === 0 && (await page.inputValue('#search')) === '');

    await page.click('text=Méthode et sources');
    await page.waitForSelector('[role="dialog"]');
    const method = await page.locator('[role="dialog"]').innerText();
    await page.keyboard.press('Escape');
    report(
      '« Méthode et sources » : les vraies sources seulement, et les deux critères de la phase 1 dans la grille',
      ['CISA', 'CERT-FR', 'ransomware.live', 'ou une alerte du CERT-FR', 'logiciel peu répandu'].every((part) => method.includes(part)) &&
        !/Mastodon|Bluesky|Cybermalveillance|rédigées par une IA|toutes les heures/.test(method) &&
        !FICTION.test(method),
    );
    await context.close();
  }

  // The sentence of the day follows the cards, and its period matches their dates.
  {
    const sentence = async (feed) => {
      const { context, page } = await openPage({ feed });
      const text = await digestText(page);
      const l = await layout(page);
      const tabs = await tabTexts(page);
      await context.close();
      return { text, l, tabs };
    };
    const quiet = await sentence(calm);
    report('Journée calme : pas de une, seulement « En bref »', quiet.l.une === null && quiet.l.two + quiet.l.three === 0 && quiet.l.brief === 3, JSON.stringify(quiet.l));
    report('Journée calme : phrase juste', quiet.text === 'Depuis hier : aucune attaque critique ni grave, 3 mineures. 3 concernent le grand public.', quiet.text);

    const alert = await sentence(alertDay);
    report('Une nouvelle attaque critique passe à la une', alert.l.une?.includes('Ferlino') && alert.l.two === 3 && alert.tabs[0] === 'Toutes 9' && alert.tabs[1] === 'Critique 2', `${alert.l.une} ; ${alert.tabs.join(', ')}`);
    report(
      'La phrase du jour suit les cartes : journée calme, puis alerte',
      quiet.text !== alert.text && alert.text === 'Depuis hier : 2 alertes critiques et 2 graves. 3 concernent le grand public.',
      alert.text,
    );

    const today = await sentence(todayOnly);
    const week = await sentence(lastWeek);
    report(
      'La période écrite correspond aux dates des cartes : « Aujourd’hui », « Depuis hier », « Ces sept derniers jours »',
      today.text === 'Aujourd’hui : 1 attaque critique et 1 grave. 2 concernent le grand public.' &&
        week.text === 'Ces sept derniers jours : 1 alerte critique et 2 graves. 2 concernent le grand public.',
      `${today.text} | ${week.text}`,
    );

    // "attaques" only when every card counted is an attack; flaws alone, or mixed: "alertes".
    const flawsOnly = { ...usual, attacks: usual.attacks.map((card) => ({ ...card, kind: 'faille' })) };
    const flaws = await sentence(flawsOnly);
    const english = await openPage({ feed: flawsOnly, locale: 'en-GB' });
    const flawsEnglish = await digestText(english.page);
    await english.context.close();
    report(
      'Phrase du jour : « alertes » tant qu’il s’agit de failles, « attaques » seulement si toutes les cartes comptées sont des attaques',
      flaws.text === 'Depuis hier : 1 alerte critique et 2 graves. 2 concernent le grand public.' &&
        flawsEnglish === 'Since yesterday: 1 critical and 2 severe alerts. 2 affect the general public.' &&
        today.text.includes('attaque critique'),
      `${flaws.text} | ${flawsEnglish} | ${today.text}`,
    );
  }

  // Same level and same day: an exploited flaw first, at the headline as in the columns.
  {
    const { context, page } = await openPage({ feed: tie });
    const order = await page.evaluate(() => ({
      une: document.querySelector('.une .une__title')?.textContent,
      two: [...document.querySelectorAll('.grid-cards--2 .card__title')].map((node) => node.textContent),
      three: [...document.querySelectorAll('.grid-cards--3 .card__title')].map((node) => node.textContent),
    }));
    await context.close();
    report(
      'À gravité et date égales, la faille exploitée passe d’abord, à la une comme ailleurs',
      order.une === 'Faille déjà exploitée' &&
        JSON.stringify(order.two) === JSON.stringify(['Alerte sans exploitation connue', 'Faille exploitée hier']) &&
        JSON.stringify(order.three) === JSON.stringify(['Significative déjà exploitée', 'Significative sans exploitation']),
      JSON.stringify(order),
    );
  }

  // A source that gives a date without a time: no hour is ever invented.
  {
    const { context, page } = await openPage({ feed: dayOnly });
    const times = await page.$$eval('#attaques time', (nodes) => nodes.map((node) => ({ text: node.textContent.trim(), at: node.getAttribute('datetime') })));
    await page.locator('#lire-test-jour').click();
    await page.waitForSelector('[role="dialog"]');
    const sheet = await page.locator('[role="dialog"]').innerText();
    await context.close();
    const text = times.map((t) => t.text).join(' ');
    report(
      'Date sans heure : « aujourd’hui », « hier », jamais une heure inventée',
      text.includes('aujourd’hui') && text.includes('hier') && !/\d\s*h\s*\d{2}/.test(text) && times.every((t) => /^\d{4}-\d{2}-\d{2}$/.test(t.at)),
      JSON.stringify(times),
    );
    report('Fiche d’une date sans heure : « Détectée le 20 novembre 2026 », chronologie sans heure', /Détectée le 20 novembre 2026(?! à)/.test(sheet) && /20 nov\./.test(sheet) && !/\d\s*h\s*\d{2}/.test(sheet.replace(/Mis à jour.*$/m, '')));

    const english = await openPage({ feed: dayOnly, locale: 'en-GB' });
    const dates = await english.page.$$eval('#attaques time', (nodes) => nodes.map((node) => node.textContent.trim()));
    await english.page.locator('#lire-test-jour').click();
    await english.page.waitForSelector('[role="dialog"]');
    const englishSheet = await english.page.locator('[role="dialog"]').innerText();
    await english.context.close();
    report(
      'Anglais, date sans heure : « today », « yesterday », « Detected on 20 November 2026 », jamais une heure',
      dates.includes('today') && dates.includes('yesterday') && /Detected on 20 November 2026(?! at)/.test(englishSheet) && !/\d{2}:\d{2}/.test(dates.join(' ')),
      dates.join(', '),
    );
  }

  // A title the collector could not translate keeps its French words, and says so to assistive
  // technologies with lang="fr".
  {
    const kept = structuredClone(usual);
    kept.attacks[0].title = { fr: 'Campagne d’hameçonnage visant les collectivités', en: 'Campagne d’hameçonnage visant les collectivités' };
    kept.attacks[0].untranslated = ['title'];
    const { context, page } = await openPage({ feed: kept, locale: 'en-GB' });
    const title = await page.evaluate(() => {
      const node = document.querySelector('.une .une__title');
      return { lang: node?.getAttribute('lang'), text: node?.textContent };
    });
    await context.close();
    report('Titre gardé dans sa langue d’origine : affiché tel quel, marqué lang="fr" dans la version anglaise', title.lang === 'fr' && title.text.startsWith('Campagne'), JSON.stringify(title));
  }

  // No card: the page says so, and invents nothing.
  {
    const quietPage = async (feed, name, locale = 'fr-FR') => {
      const { context, page, errors } = await openPage({ feed, waitFor: '.state', locale });
      const result = {
        state: clean(await page.locator('.state').first().textContent()),
        updated: await updatedText(page),
        tabs: await page.locator('.tab').count(),
        digest: await page.locator('.digest__text').count(),
        text: await page.evaluate(() => document.body.innerText),
        errors: errors.filter((error) => !/404|Failed to load resource/.test(error)),
      };
      if (name) {
        const lang = locale.slice(0, 2);
        await page.screenshot({ path: path.join(captures, `${name}-1440-${lang}.png`), fullPage: true });
        await page.setViewportSize({ width: 390, height: 844 });
        await page.screenshot({ path: path.join(captures, `${name}-390-${lang}.png`), fullPage: true });
      }
      await page.click('.site-footer .link');
      await page.waitForSelector('[role="dialog"]');
      result.text += await page.locator('[role="dialog"]').innerText();
      await context.close();
      return result;
    };
    const absent = await quietPage(404, 'vide');
    const absentEnglish = await quietPage(404, 'vide', 'en-GB');
    report(
      'Anglais, sans data/cards.json : « No attack recorded at the moment. », sans heure',
      absentEnglish.state === 'No attack recorded at the moment.' && absentEnglish.updated === '' && !FICTION.test(absentEnglish.text) && !FRENCH_UI.test(absentEnglish.text),
      absentEnglish.state,
    );
    report(
      'Sans data/cards.json : « Aucune attaque recensée pour le moment », sans heure, sans onglets ni phrase',
      absent.state === 'Aucune attaque recensée pour le moment.' && absent.updated === '' && absent.tabs === 0 && absent.digest === 0 && absent.errors.length === 0,
      JSON.stringify({ ...absent, text: undefined }),
    );
    report('Aucun mot « démo », « simulation » ou « fictif » sur le site, panneau « Méthode et sources » compris', !FICTION.test(absent.text), FICTION.exec(absent.text)?.[0] ?? '');
    const htmlInstead = await quietPage('<!doctype html><title>Page</title>');
    report('Une page HTML à la place du fichier compte comme l’absence de fichier', htmlInstead.state === 'Aucune attaque recensée pour le moment.' && htmlInstead.updated === '');
    const none = await quietPage(emptyFeed);
    report('Fichier sans attaque : même message, avec l’heure réelle de la collecte', none.state === 'Aucune attaque recensée pour le moment.' && none.updated === 'Mis à jour à 14 h 50' && none.tabs === 0, `${none.state} ; ${none.updated}`);
    const broken = await quietPage('{pas du json');
    report('Fichier illisible : un message d’erreur, pas « aucune attaque »', broken.state.startsWith('Impossible de charger les attaques') && broken.updated === 'Données indisponibles', broken.state);
  }

  // The file is read again every five minutes, and when the tab comes back.
  {
    let current = usual;
    const { context, page, requests } = await openPage({ feed: () => current, timers: 'fake', waitFor: null });
    await until(page, () => document.querySelectorAll('.tab').length > 0);
    const before = { updated: await updatedText(page), tabs: await tabTexts(page) };
    current = { generated_at: new Date(NOW + 3 * 60_000).toISOString(), attacks: [buildAlert(0, NOW + 2 * 60_000), ...usual.attacks] };
    await page.clock.runFor(5 * 60_000 + 1_000);
    const refreshed = await until(page, () => document.querySelector('.tab')?.textContent.includes('9'));
    const after = { updated: await updatedText(page), reads: requests.feed };
    await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    const end = Date.now() + 5000;
    while (Date.now() < end && requests.feed <= after.reads) await new Promise((resolve) => setTimeout(resolve, 100));
    const again = requests.feed > after.reads;
    await context.close();
    report(
      'Le fichier est relu toutes les 5 minutes et au retour sur l’onglet : nouvelle carte, nouvelle heure',
      before.tabs[0] === 'Toutes 8' && before.updated === 'Mis à jour à 14 h 48' && refreshed && after.updated === 'Mis à jour à 15 h 03' && again,
      `${before.updated} → ${after.updated}, ${requests.feed} lectures`,
    );
  }

  // Detail panel: the only movement, three ways to close, focus back, checklist kept.
  {
    const { context, page } = await openPage();
    const opener = page.locator('.une .link');
    const openerId = await opener.getAttribute('id');
    const failures = [];
    let moving = 0;
    for (const how of ['Fermer', 'Échap', 'clic à l’extérieur']) {
      await opener.click();
      await page.waitForSelector('[role="dialog"]');
      moving = Math.max(moving, await page.evaluate(() => document.getAnimations().length));
      if (clean(await page.evaluate(() => document.activeElement?.textContent)) !== 'Fermer') failures.push(`${how} : focus`);
      if (how === 'Fermer') await page.click('.drawer-close');
      if (how === 'Échap') await page.keyboard.press('Escape');
      if (how === 'clic à l’extérieur') await page.mouse.click(100, 450);
      await page.waitForSelector('[role="dialog"]', { state: 'detached' });
      if (!(await page.evaluate((id) => document.activeElement?.id === id, openerId))) failures.push(`${how} : retour du focus`);
    }
    report('Tiroir : se ferme par « Fermer », Échap et clic extérieur ; le focus revient', failures.length === 0, failures.join('; '));
    report('L’ouverture du tiroir est le seul mouvement', moving > 0, `${moving} animation(s) pendant l’ouverture`);

    await opener.click();
    await page.waitForSelector('[role="dialog"]');
    await page.locator('.steps label').first().click();
    await page.keyboard.press('Escape');
    await page.waitForSelector('[role="dialog"]', { state: 'detached' });
    await opener.click();
    await page.waitForSelector('[role="dialog"]');
    report('Étapes « Que faire » cochables, gardées sur l’appareil', await page.locator('.steps input').first().isChecked());
    await context.close();
  }

  // Keyboard only.
  {
    const { context, page } = await openPage();
    const seen = [];
    for (let i = 0; i < 60; i += 1) {
      await page.keyboard.press('Tab');
      const info = await page.evaluate(() => {
        const el = document.activeElement;
        const s = getComputedStyle(el);
        const kind = el.id === 'search' ? 'search' : el.classList.contains('tab') ? 'tab' : el.type === 'checkbox' ? 'checkbox' : el.id?.startsWith('lire-') ? 'read' : el.tagName.toLowerCase();
        return { key: [...document.querySelectorAll('*')].indexOf(el), kind, ring: s.outlineStyle === 'solid' && s.outlineWidth === '2px' };
      });
      if (info.kind === 'body' || seen.some((s) => s.key === info.key)) break;
      seen.push(info);
    }
    const count = (kind) => seen.filter((s) => s.kind === kind).length;
    report('Clavier : recherche, onglets, case, chaque « Lire »', count('search') === 1 && count('tab') === 5 && count('checkbox') === 1 && count('read') === 8, seen.map((s) => s.kind).join(' > '));
    report('Focus visible (contour noir de 2 px) partout', seen.every((s) => s.ring));
    await context.close();
  }

  // Reduced motion: even the panel appears without moving.
  {
    const { context, page } = await openPage({ reduce: true });
    await page.locator('.une .link').click();
    await page.waitForSelector('[role="dialog"]');
    report('Avec prefers-reduced-motion, le tiroir apparaît sans bouger', (await page.evaluate(() => document.getAnimations().length)) === 0);
    await context.close();
  }

  // A feed with missing information and dangerous links, as a real one may have.
  {
    const feed = structuredClone(usual);
    const [first, second, third, fourth, fifth] = feed.attacks;
    delete first.attacker;
    first.sources = [
      { name: 'Source de test', title: 'Lien normal', url: 'https://example.org/article', official: true },
      { name: 'Lien piégé', title: 'javascript:', url: 'javascript:alert(1)', official: false },
      { name: 'Site de rançonneurs', title: '.onion', url: 'http://abcdefgh.onion/fuite', official: false },
    ];
    delete second.method;
    delete second.lede;
    second.summary = [];
    third.victim = {};
    third.attacker = { name: 'Groupe test', country: 'Pays test', status: 'presume', source: null };
    delete fourth.loot;
    delete fifth.reliability; // a confirmed card whose feed forgot the field

    const { context, page, errors } = await openPage({ feed });
    await page.screenshot({ path: path.join(captures, 'test-incomplet-1440.png'), fullPage: true });
    const text = await page.evaluate(() => document.body.innerText);
    const csp = await page.evaluate(() => document.querySelector('meta[http-equiv="Content-Security-Policy"]')?.content ?? '');
    const articles = await page.locator(CARDS).count();
    await page.locator('#lire-test-telecomx').click();
    await page.waitForSelector('[role="dialog"]');
    const links = await page.$$eval('.sources a', (anchors) => anchors.map((a) => ({ href: a.href, rel: a.rel, target: a.target })));
    const mitre = await page.$$eval('.tech a', (anchors) => anchors.map((a) => a.href));
    await context.close();

    const phone = await openPage({ feed, width: 390, height: 844 });
    await phone.page.screenshot({ path: path.join(captures, 'test-incomplet-390.png'), fullPage: true });
    await phone.context.close();

    report('Flux de test incomplet : toutes les attaques s’affichent', articles === 8, `${articles}`);
    report('Cartes incomplètes : « Non communiqué » à la place de chaque information manquante', (text.match(/Non communiqué/g) ?? []).length >= 5);
    report('Pays donné par une source : écrit en toutes lettres', text.includes('Groupe test (Pays test)'));
    report('Fiabilité absente du flux : traitée comme une rumeur, jamais comme confirmée', /Rumeur, non confirmée/.test(text));
    report('Liens des sources : seul le lien web reste, ouvert à part', links.length === 1 && links[0].href === 'https://example.org/article' && links[0].rel === 'noopener noreferrer' && links[0].target === '_blank', JSON.stringify(links));
    report('Techniques MITRE ATT&CK liées à attack.mitre.org', mitre.length > 0 && mitre.every((href) => href.startsWith('https://attack.mitre.org/techniques/')));
    report('Content-Security-Policy présente', csp.includes("connect-src 'self'"), csp);
    report('Aucune erreur dans la console, CSP comprise', errors.length === 0, errors.join(' | '));
  }

  // Security: hostile cards and search, hostile address and storage, huge or broken files.
  {
    const PAYLOADS = [
      '<script>window.__xss = 1; alert("xss")</script>',
      '<img src=x onerror="window.__xss = 1; alert(\'xss\')">',
      '<svg onload="window.__xss = 1; alert(\'xss\')"></svg>',
      '"><img src=x onerror=alert(1)>',
      "'><svg/onload=alert(1)>",
      'javascript:alert(1)',
      '<iframe srcdoc="<script>alert(1)</script>"></iframe>',
      '<a href="javascript:alert(1)">lien</a>',
    ];
    const LINKS = [
      'javascript:alert(1)',
      'JAVASCRIPT:alert(1)',
      ' javascript:alert(1)',
      'data:text/html,<script>alert(1)</script>',
      'vbscript:msgbox(1)',
      'file:///C:/Windows/win.ini',
      '//evil.example/x',
      'https://user:pass@example.org/',
      'https://abcdefgh.onion/',
      'https://xn--80ak6aa92e.com/',
      'https://example.org/"onmouseover="alert(1)',
      'https://example.org/sain',
    ];
    let count = 0;
    const payload = () => PAYLOADS[count++ % PAYLOADS.length];
    const both = () => ({ fr: payload(), en: payload() });
    const hostile = structuredClone(usual);
    hostile.attacks.forEach((card, index) => {
      Object.assign(card, {
        title: both(),
        lede: both(),
        severity_reason: both(),
        method: both(),
        loot: both(),
        am_i_affected: both(),
        action: both(),
        sector: both(),
        reliability_source: payload(),
        summary: [both(), both()],
        protection_steps: [both(), both()],
        timeline: (card.timeline ?? []).map((event) => ({ ...event, label: both() })),
        victim: { ...card.victim, label: both() },
        attacker: { name: both(), country: both(), status: 'presume', source: payload() },
        technical: { cves: [payload(), 'CVE-2026-1234'], software: [both()], techniques: [{ id: payload(), name: payload() }, { id: 'T1566', name: both() }] },
        sources: LINKS.map((url, i) => ({ name: payload(), title: both(), url, official: i % 2 === 0 })),
      });
      if (index === 1) card.id = 'x"><img src=x onerror=alert(1)>';
    });

    const anchors = [];
    const visit = async (locale) => {
      const { context, page, errors } = await openPage({ feed: hostile, locale });
      for (const opener of await page.locator('[id^="lire-"]').all()) {
        await opener.click();
        await page.waitForSelector('[role="dialog"]');
        anchors.push(...(await page.$$eval('[role="dialog"] a[href]', (list) => list.map((a) => ({ href: a.getAttribute('href'), target: a.target, rel: a.rel })))));
        await page.keyboard.press('Escape');
        await page.waitForSelector('[role="dialog"]', { state: 'detached' });
      }
      await page.click('.site-footer .link');
      await page.waitForSelector('[role="dialog"]');
      await page.keyboard.press('Escape');
      await page.waitForSelector('[role="dialog"]', { state: 'detached' });
      for (const text of PAYLOADS) {
        await page.fill('#search', text);
        await page.waitForTimeout(50);
      }
      await page.fill('#search', '');
      const state = await page.evaluate(() => ({
        xss: window.__xss ?? 0,
        scripts: document.querySelectorAll('script').length,
        inline: [...document.scripts].filter((script) => !script.src).length,
        injected: document.querySelectorAll('img, svg, iframe, object, embed, [onerror], [onload], [onmouseover], [srcdoc]').length,
        shownAsText: document.body.innerText.includes('<img src=x onerror'),
        cookie: document.cookie,
      }));
      const cookies = await context.cookies();
      await context.close();
      return { ...state, cookies: cookies.length, errors: errors.filter((error) => !/Failed to load resource/.test(error)).length };
    };
    const fr = await visit('fr-FR');
    const en = await visit('en-GB');
    report(
      'XSS : <script>, <img onerror>, <svg onload>, javascript: dans chaque champ de cards.json et dans la recherche, en français et en anglais : aucune boîte de dialogue, aucun élément créé, texte affiché tel quel',
      dialogs.length === 0 && [fr, en].every((s) => s.xss === 0 && s.injected === 0 && s.inline === 0 && s.scripts === 1 && s.shownAsText && s.errors === 0),
      JSON.stringify({ dialogs: dialogs.length, fr, en }),
    );
    const hrefs = [...new Set(anchors.map((anchor) => anchor.href))].sort();
    const badLinks = anchors.filter((a) => a.target !== '_blank' || !a.rel.split(/\s+/).includes('noopener') || !a.rel.split(/\s+/).includes('noreferrer'));
    report(
      'Liens des cartes piégées : seuls https://example.org/sain et attack.mitre.org restent, tous en target="_blank" rel="noopener noreferrer"',
      badLinks.length === 0 && JSON.stringify(hrefs) === JSON.stringify(['https://attack.mitre.org/techniques/T1566/', 'https://example.org/sain']),
      hrefs.join(' '),
    );
    report('Aucun cookie, ni lu ni posé', [fr, en].every((s) => s.cookie === '' && s.cookies === 0));
  }

  // Control: in the built page, the CSP and Trusted Types really block innerHTML, eval, new
  // Function and inline scripts, and each block is seen by the checks above.
  {
    const seen = [];
    const { context, page } = await openPage({ seenViolations: seen });
    // The attempts run from a timer, as page code: code run directly by the test tool is exempt
    // from the eval rule of the CSP.
    const blocked = await page.evaluate(() => new Promise((resolve) => setTimeout(() => {
      const attempts = {
        innerHTML: () => {
          document.body.appendChild(document.createElement('div')).innerHTML = '<img src=x>';
        },
        eval: () => window.eval('1 + 1'),
        newFunction: () => new Function('return 1')(),
        inlineScript: () => {
          const script = document.createElement('script');
          script.textContent = 'window.__inline = 1';
          document.body.append(script);
        },
      };
      resolve(
        Object.fromEntries(
          Object.entries(attempts).map(([name, attempt]) => {
            try {
              attempt();
              return [name, false];
            } catch {
              return [name, true];
            }
          }),
        ),
      );
    }, 0)));
    await page.waitForTimeout(300);
    const ran = await page.evaluate(() => ({ inline: window.__inline ?? 0, img: document.querySelectorAll('img').length }));
    await context.close();
    report(
      'Contrôle : la page construite bloque innerHTML, eval, new Function et les scripts en ligne, et chaque blocage est vu',
      Object.values(blocked).every(Boolean) && ran.inline === 0 && ran.img === 0 && seen.length >= 4,
      `${JSON.stringify(blocked)} ; ${seen.length} violation(s) vue(s)`,
    );
  }

  // No address parameter or fragment changes the data source.
  {
    const { context, page, requests } = await openPage({
      address: '?data=https://evil.example/cards.json&src=//evil.example/x.json&feed=data:application/json,{}#https://evil.example/cards.json',
    });
    const tabs = await tabTexts(page);
    await context.close();
    const feedUrl = new URL('data/cards.json', base).href;
    report(
      'Paramètres et fragment d’adresse ignorés : les données viennent toujours de data/cards.json du site',
      requests.urls.length > 0 && requests.urls.every((url) => url === feedUrl) && tabs[0] === 'Toutes 8',
      `${[...new Set(requests.urls)].join(' ')} ; ${tabs[0]}`,
    );
  }

  // Stored language: only "fr" or "en", anything else is ignored.
  {
    const seen = [];
    for (const stored of ['<img src=x onerror=alert(1)>', 'EN', 'en ', '"en"', 'javascript:alert(1)', '__proto__']) {
      const { context, page } = await openPage({ stored });
      seen.push(await page.evaluate(() => ({ lang: document.documentElement.lang, img: document.querySelectorAll('img').length })));
      await context.close();
    }
    report('Valeur de langue trafiquée dans localStorage : ignorée, sans effet', seen.every((s) => s.lang === 'fr' && s.img === 0), JSON.stringify(seen));
  }

  // A huge, deeply nested, oddly shaped or unreadable cards.json: a clear message, no crash.
  {
    const huge = structuredClone(usual);
    huge.attacks[0].summary = [{ fr: 'x'.repeat(6 * 1024 * 1024), en: 'x' }];
    const cases = {
      'énorme (6 Mo)': JSON.stringify(huge),
      'imbriqué 200 000 fois': '['.repeat(200_000) + ']'.repeat(200_000),
      'attaques qui ne sont pas une liste': JSON.stringify({ generated_at: usual.generated_at, attacks: 'aucune' }),
      'tableau seul': '[]',
      'caractères nuls': '\u0000\u0000{',
    };
    const states = {};
    for (const [name, body] of Object.entries(cases)) {
      const { context, page, errors } = await openPage({ feed: body, waitFor: '.state' });
      states[name] = { state: clean(await page.locator('.state').first().textContent()).slice(0, 40), errors: errors.length };
      await context.close();
    }
    report(
      'cards.json énorme, trop imbriqué, de forme inattendue ou illisible : « Impossible de charger les attaques… », aucun plantage',
      Object.values(states).every((s) => s.state.startsWith('Impossible de charger les attaques') && s.errors === 0),
      JSON.stringify(states),
    );
  }

  // The real cards, when the collector has written them, in French and in English.
  if (existsSync(realFile)) {
    const real = JSON.parse(await readFile(realFile, 'utf8'));
    const seen = {};
    for (const [lang, locale, all] of [
      ['fr', 'fr-FR', 'Toutes'],
      ['en', 'en-GB', 'All'],
    ]) {
      const { context, page, errors } = await openPage({ feed: null, timers: 'real', waitFor: `${CARDS}, .state`, locale });
      await page.screenshot({ path: path.join(captures, `reel-1440-${lang}.png`), fullPage: true });
      const shown = await page.locator(CARDS).count();
      const total = (await tabTexts(page))[0] ?? '';
      const stamp = (await page.locator('.site-header__updated time').getAttribute('datetime').catch(() => null)) ?? '';
      const text = await page.evaluate(() => document.body.innerText);
      const sentence = shown > 0 ? await digestText(page) : '';
      await page.setViewportSize({ width: 390, height: 844 });
      await page.screenshot({ path: path.join(captures, `reel-390-${lang}.png`), fullPage: true });
      await context.close();
      seen[lang] = {
        ok: (shown === 0 || total === `${all} ${shown}`) && Date.parse(stamp) === Date.parse(real.generated_at) && errors.length === 0,
        other: lang === 'en' ? FRENCH_UI.exec(text)?.[0] : ENGLISH_UI.exec(text)?.[0],
        shown,
        sentence,
      };
    }
    report(
      `Vraies cartes de public/data/cards.json, en français et en anglais : ${seen.fr.shown} affichées, heure de la collecte, aucune erreur`,
      seen.fr.ok && seen.en.ok && seen.fr.shown === seen.en.shown && !seen.fr.other && !seen.en.other,
      `collecte ${real.generated_at}${seen.en.other ? ` ; en anglais : « ${seen.en.other} »` : ''}${seen.fr.other ? ` ; en français : « ${seen.fr.other} »` : ''}`,
    );
    if (real.attacks.length > 0 && real.attacks.every((card) => card.kind === 'faille')) {
      report(
        'Vraies cartes, toutes des failles : la phrase du jour parle d’« alertes », jamais d’« attaques »',
        !/attaque/i.test(seen.fr.sentence) && !/attack/i.test(seen.en.sentence) && /alerte|aucune/.test(seen.fr.sentence),
        `${seen.fr.sentence} | ${seen.en.sentence}`,
      );
    }
  } else {
    console.log('(public/data/cards.json absent : pas de capture des vraies cartes)');
  }
} finally {
  await browser.close();
  await previewServer.close();
  await rm(out, { recursive: true, force: true });
}

report('Aucune requête vers un autre domaine', offsite.length === 0, [...new Set(offsite)].join(' '));
report('Aucune violation de la CSP ni des Trusted Types, sur toutes les pages ouvertes', violations.length === 0, [...new Set(violations)].slice(0, 3).join(' | '));
report('Aucune boîte de dialogue ouverte, sur toutes les pages ouvertes', dialogs.length === 0, dialogs.slice(0, 3).join(' | '));

const failed = results.filter((ok) => !ok).length;
console.log(`\n${results.length - failed}/${results.length} vérifications réussies. Captures : ${captures}`);
process.exitCode = failed === 0 ? 0 : 1;
