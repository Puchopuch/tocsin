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
import { build, preview } from 'vite';
import { APP_NAME } from '../src/config.js';
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
const FICTION = /\bd[ée]mo\b|\bsimul(?:ation|ations|er|ée|ées)\b|\bfictif|\bfictive|données fictives/i;

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
    if (INVENTED_NAMES.some((invention) => source.includes(invention)) || /fixtures/.test(source)) invented.push(name);
  }
  report('La phrase du jour n’est écrite nulle part dans le code', written.length === 0, written.join(', '));
  report('Aucune donnée de test dans src/ : elles vivent dans scripts/fixtures.mjs', invented.length === 0, invented.join(', '));
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

const previewServer = await preview({ root, logLevel: 'error', build: { outDir: out }, preview: { port: 4199, strictPort: false } });
const base = previewServer.resolvedUrls.local[0];
const browser = await chromium.launch({ channel: process.env.CHECK_BROWSER || undefined });
const offsite = [];

/**
 * A page of the built site. `feed` stands for data/cards.json: an object, an HTTP status, raw
 * text, a function returning one of these at each request, or null for the real file. `timers`:
 * "fixed" (the date is NOW), "fake" (NOW, and time moves only when the test says so) or "real".
 */
async function openPage({ feed = usual, width = 1440, height = 900, reduce = false, waitFor = CARDS, timers = 'fixed' } = {}) {
  const context = await browser.newContext({
    viewport: { width, height },
    reducedMotion: reduce ? 'reduce' : 'no-preference',
    locale: 'fr-FR',
    timezoneId: 'Europe/Paris',
  });
  const page = await context.newPage();
  const errors = [];
  const requests = { feed: 0 };
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (!['data:', 'blob:'].includes(url.protocol) && url.origin !== new URL(base).origin) offsite.push(url.href);
  });
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(String(error)));
  await page.route('**/data/cards.json', (route) => {
    requests.feed += 1;
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
  await page.goto(base);
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
  // Screenshots: the usual day, a calm day and the detail panel, with test cards.
  {
    const shoot = async (name, { feed = usual, width, height, act, full = true }) => {
      const { context, page } = await openPage({ feed, width, height });
      if (act) await act(page);
      await page.waitForTimeout(400);
      await page.screenshot({ path: path.join(captures, name), fullPage: full });
      await context.close();
    };
    const sheet = async (page) => {
      await page.locator('.une .link').click();
      await page.waitForSelector('[role="dialog"]');
      await page.waitForTimeout(600); // let the panel finish sliding in
    };
    for (const [width, height] of [
      [1440, 900],
      [390, 844],
    ]) {
      await shoot(`test-${width}.png`, { width, height });
      await shoot(`test-calme-${width}.png`, { feed: calm, width, height });
      await shoot(`test-tiroir-${width}.png`, { width, height, act: sheet, full: false });
    }
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
    report('Phrase calculée sur les cartes', (await digestText(page)) === 'Depuis hier : 1 attaque critique et 2 graves. 2 concernent le grand public.', await digestText(page));
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
      quiet.text !== alert.text && alert.text === 'Depuis hier : 2 attaques critiques et 2 graves. 3 concernent le grand public.',
      alert.text,
    );

    const today = await sentence(todayOnly);
    const week = await sentence(lastWeek);
    report(
      'La période écrite correspond aux dates des cartes : « Aujourd’hui », « Depuis hier », « Ces sept derniers jours »',
      today.text === 'Aujourd’hui : 1 attaque critique et 1 grave. 2 concernent le grand public.' &&
        week.text === 'Ces sept derniers jours : 1 attaque critique et 2 graves. 2 concernent le grand public.',
      `${today.text} | ${week.text}`,
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
  }

  // No card: the page says so, and invents nothing.
  {
    const quietPage = async (feed, name) => {
      const { context, page, errors } = await openPage({ feed, waitFor: '.state' });
      const result = {
        state: clean(await page.locator('.state').first().textContent()),
        updated: await updatedText(page),
        tabs: await page.locator('.tab').count(),
        digest: await page.locator('.digest__text').count(),
        text: await page.evaluate(() => document.body.innerText),
        errors: errors.filter((error) => !/404|Failed to load resource/.test(error)),
      };
      if (name) {
        await page.screenshot({ path: path.join(captures, `${name}-1440.png`), fullPage: true });
        await page.setViewportSize({ width: 390, height: 844 });
        await page.screenshot({ path: path.join(captures, `${name}-390.png`), fullPage: true });
      }
      await page.click('text=Méthode et sources');
      await page.waitForSelector('[role="dialog"]');
      result.text += await page.locator('[role="dialog"]').innerText();
      await context.close();
      return result;
    };
    const absent = await quietPage(404, 'vide');
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

  // The real cards, when the collector has written them.
  if (existsSync(realFile)) {
    const real = JSON.parse(await readFile(realFile, 'utf8'));
    const { context, page, errors } = await openPage({ feed: null, timers: 'real', waitFor: `${CARDS}, .state` });
    await page.screenshot({ path: path.join(captures, 'reel-1440.png'), fullPage: true });
    const shown = await page.locator(CARDS).count();
    const total = (await tabTexts(page))[0] ?? '';
    const stamp = (await page.locator('.site-header__updated time').getAttribute('datetime').catch(() => null)) ?? '';
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(captures, 'reel-390.png'), fullPage: true });
    await context.close();
    report(
      `Vraies cartes de public/data/cards.json : ${shown} affichées, heure de la collecte, aucune erreur`,
      (shown === 0 || total === `Toutes ${shown}`) && Date.parse(stamp) === Date.parse(real.generated_at) && errors.length === 0,
      `${total} ; collecte ${real.generated_at}`,
    );
  } else {
    console.log('(public/data/cards.json absent : pas de capture des vraies cartes)');
  }
} finally {
  await browser.close();
  await previewServer.close();
  await rm(out, { recursive: true, force: true });
}

report('Aucune requête vers un autre domaine', offsite.length === 0, [...new Set(offsite)].join(' '));

const failed = results.filter((ok) => !ok).length;
console.log(`\n${results.length - failed}/${results.length} vérifications réussies. Captures : ${captures}`);
process.exitCode = failed === 0 ? 0 : 1;
