// Automated browser checks of the frontend, run with `npm run check`.
//
// It starts the dev server (demo data), then builds the real site into a temporary folder and
// serves it with a test feed (some cards miss information), drives a browser with Playwright,
// prints one line per check and saves screenshots in captures/ (ignored by git).
//
// Browser: Playwright's own Chromium (`npx playwright install chromium`, once), or a Chrome or
// Edge already installed: CHECK_BROWSER=chrome npm run check (or msedge).

import { mkdir, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { build, createServer, preview } from 'vite';
import { APP_NAME } from '../src/config.js';
import { buildDemoFeed } from '../src/data/demo.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const captures = path.join(root, 'captures');
const realOut = path.join(os.tmpdir(), 'tocsin-check-dist');
const WIDTHS = [360, 390, 768, 1024, 1440];

// The only colours allowed by the brief, as the browser reports them.
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

const results = [];
function report(label, ok, detail = '') {
  results.push(ok);
  console.log(`${ok ? 'OK  ' : 'FAIL'}  ${label}${detail ? `  (${detail})` : ''}`);
}

const browser = await chromium.launch({ channel: process.env.CHECK_BROWSER || undefined });
const offsite = [];

async function openPage(base, { width = 1440, height = 900, reduce = false, waitFor = '#attaques article, .brief__row', context: shared } = {}) {
  const context =
    shared ??
    (await browser.newContext({
      viewport: { width, height },
      reducedMotion: reduce ? 'reduce' : 'no-preference',
      locale: 'fr-FR',
      timezoneId: 'Europe/Paris',
    }));
  const page = await context.newPage();
  const errors = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (!['data:', 'blob:'].includes(url.protocol) && url.origin !== new URL(base).origin) offsite.push(url.href);
  });
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(String(error)));
  await page.goto(base);
  if (waitFor) await page.waitForSelector(waitFor);
  await page.evaluate(() => document.fonts.ready);
  return { context, page, errors };
}

const clean = (text) => (text ?? '').replace(/\s+/g, ' ').trim();
const tabTexts = (page) => page.$$eval('.tab', (tabs) => tabs.map((tab) => tab.textContent.replace(/\s+/g, ' ').trim()));
const digestText = (page) => page.locator('.digest__text').textContent().then(clean);
const layout = (page) =>
  page.evaluate(() => ({
    une: document.querySelector('.une .une__title')?.textContent ?? null,
    two: document.querySelectorAll('.grid-cards--2 > .card').length,
    three: document.querySelectorAll('.grid-cards--3 > .card').length,
    brief: document.querySelectorAll('.brief__row').length,
    briefHeading: document.querySelector('#en-bref') !== null,
  }));

/** Every rule of the brief that can be read on the page itself. */
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

// ---------------------------------------------------------------------------------------------
// Demo mode, on the dev server

const server = await createServer({ root, logLevel: 'error', server: { port: 5199, strictPort: false } });
await server.listen();
const demoBase = server.resolvedUrls.local[0];

try {
  await rm(captures, { recursive: true, force: true });
  await mkdir(captures, { recursive: true });

  // Screenshots asked by the brief, demo mode.
  {
    const shoot = async (name, { width, height, act, full = true }) => {
      const { context, page } = await openPage(demoBase, { width, height });
      if (act) await act(page);
      await page.waitForTimeout(400);
      await page.screenshot({ path: path.join(captures, name), fullPage: full });
      await context.close();
    };
    const calm = (page) => page.click('text=Simuler une journée calme');
    const sheet = async (page) => {
      await page.locator('.une .link').click();
      await page.waitForSelector('[role="dialog"]');
      await page.waitForTimeout(600); // let the panel finish sliding in
    };
    for (const [width, height] of [
      [1440, 900],
      [390, 844],
    ]) {
      await shoot(`demo-${width}.png`, { width, height });
      await shoot(`demo-calme-${width}.png`, { width, height, act: calm });
      await shoot(`demo-tiroir-${width}.png`, { width, height, act: sheet, full: false });
    }
  }

  // The sentence of the day is never written in the code: no file of src/ contains one.
  {
    const { readdir, readFile } = await import('node:fs/promises');
    const files = (await readdir(path.join(root, 'src'), { recursive: true })).filter((file) => /\.(js|jsx)$/.test(file));
    const written = [];
    for (const file of files) {
      const source = await readFile(path.join(root, 'src', file), 'utf8');
      if (/Depuis hier\s*:\s*\d|\d+ attaques? (critiques?|graves?|significatives?|mineures?)/.test(source)) written.push(file);
    }
    report('La phrase du jour n’est écrite nulle part dans le code', written.length === 0, written.join(', '));
  }

  // Widths: no sideways scroll, one-line header, one column on phones with the headline first.
  {
    const problems = [];
    for (const width of WIDTHS) {
      const { context, page } = await openPage(demoBase, { width, height: 900 });
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

  // Layout and sentence of the usual day.
  {
    const { context, page, errors } = await openPage(demoBase);
    const tabs = await tabTexts(page);
    report('Onglets : Toutes 8, Critique 1, Grave 2, Significative 3, Mineure 2', JSON.stringify(tabs) === JSON.stringify(['Toutes 8', 'Critique 1', 'Grave 2', 'Significative 3', 'Mineure 2']), tabs.join(', '));
    report('Phrase calculée sur les cartes', (await digestText(page)) === 'Depuis hier : 1 attaque critique et 2 graves. 2 concernent le grand public.', await digestText(page));
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
    report('Tailles 14, 16, 22 et 40 px ; graisses 300, 400 et 700', audit.sizes.every((s) => ['14px', '16px', '22px', '40px'].includes(s)) && audit.weights.every((w) => ['300', '400', '700'].includes(w)), `${audit.sizes.join(' ')} · ${audit.weights.join(' ')}`.replace(' · ', ' / '));

    const text = await page.evaluate(() => document.body.innerText);
    report('Pas de « · », de flèche, de badge « Confirmé » ni d’« En direct »', !/[·→]/.test(text) && !/\bConfirmé\b/.test(text) && !/en direct/i.test(text));
    report('Statut seulement quand il n’est pas confirmé', /Revendiqué, non confirmé/.test(text) && /Présumé, non confirmé/.test(text) && /Rumeur vue sur X, non confirmée/.test(text));
    report('Information absente : « Non communiqué », la ligne reste', (text.match(/Non communiqué/g) ?? []).length >= 3);
    report(`Nom tiré de APP_NAME (« ${APP_NAME} ») dans l’en-tête et le titre de page`, clean(await page.locator('.site-header__name').textContent()) === APP_NAME && (await page.title()).startsWith(APP_NAME));
    report('Mode démo : ligne « Données fictives » et deux petits liens', (await page.locator('.demo-line').textContent()).includes('Données fictives') && (await page.locator('.demo-line button').count()) === 2);
    report('Aucune animation au chargement', (await page.evaluate(() => document.getAnimations().length)) === 0);
    report('Aucune erreur dans la console (démo)', errors.length === 0, errors.join(' | '));

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
    report('« Grand public uniquement » : les attaques d’entreprises disparaissent, la phrase suit', publicTabs[0] === 'Toutes 6' && publicDigest === 'Depuis hier : 1 attaque critique et 1 grave. 2 concernent le grand public.', `${publicTabs[0]} ; ${publicDigest}`);

    await page.keyboard.press('/');
    const slash = await page.evaluate(() => document.activeElement?.id === 'search');
    await page.keyboard.type('telecomx');
    const searched = await layout(page);
    await page.keyboard.press('Escape');
    report('Recherche instantanée, « / » pour y aller, Échap pour effacer', slash && searched.une?.includes('TelecomX') && searched.two + searched.three + searched.brief === 0 && (await page.inputValue('#search')) === '');

    await page.click('text=Simuler une journée calme');
    const calm = await layout(page);
    const calmDigest = await digestText(page);
    report('Journée calme : pas de une, seulement « En bref »', calm.une === null && calm.two + calm.three === 0 && calm.brief === 3, JSON.stringify(calm));
    report('Journée calme : phrase juste', calmDigest === 'Depuis hier : aucune attaque critique ni grave, 3 mineures. 3 concernent le grand public.', calmDigest);
    await page.click('text=Revenir à la journée habituelle');

    const usualDigest = await digestText(page);
    await page.click('text=Simuler une alerte');
    const simulated = await layout(page);
    const simulatedTabs = await tabTexts(page);
    const simulatedDigest = await digestText(page);
    report('« Simuler une alerte » : la nouvelle attaque critique passe à la une', simulated.une?.includes('Ferlino') && simulated.two === 3 && simulatedTabs[0] === 'Toutes 9' && simulatedTabs[1] === 'Critique 2', `${simulated.une} ; ${simulatedTabs.join(', ')}`);
    report(
      'La phrase du jour suit les cartes : journée calme, puis alerte simulée',
      calmDigest !== usualDigest &&
        simulatedDigest !== usualDigest &&
        simulatedDigest === 'Depuis hier : 2 attaques critiques et 2 graves. 3 concernent le grand public.',
      simulatedDigest,
    );
    report('Aucune animation d’entrée pour la nouvelle carte', (await page.evaluate(() => document.getAnimations().length)) === 0);
    await context.close();
  }

  // Detail panel: the only movement, three ways to close, focus back, checklist kept.
  {
    const { context, page } = await openPage(demoBase);
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
    const { context, page } = await openPage(demoBase);
    const seen = [];
    for (let i = 0; i < 60; i += 1) {
      await page.keyboard.press('Tab');
      const info = await page.evaluate(() => {
        const el = document.activeElement;
        const s = getComputedStyle(el);
        const kind = el.id === 'search' ? 'search' : el.classList.contains('tab') ? 'tab' : el.type === 'checkbox' ? 'checkbox' : el.id?.startsWith('lire-') ? 'read' : el.closest('.demo-line') ? 'demo' : el.tagName.toLowerCase();
        return { key: [...document.querySelectorAll('*')].indexOf(el), kind, ring: s.outlineStyle === 'solid' && s.outlineWidth === '2px' };
      });
      if (info.kind === 'body' || seen.some((s) => s.key === info.key)) break;
      seen.push(info);
    }
    const count = (kind) => seen.filter((s) => s.kind === kind).length;
    report('Clavier : recherche, liens de démo, onglets, case, chaque « Lire »', count('search') === 1 && count('demo') === 2 && count('tab') === 5 && count('checkbox') === 1 && count('read') === 8, seen.map((s) => s.kind).join(' > '));
    report('Focus visible (contour noir de 2 px) partout', seen.every((s) => s.ring));
    await context.close();
  }

  // Reduced motion: even the panel appears without moving.
  {
    const { context, page } = await openPage(demoBase, { reduce: true });
    await page.locator('.une .link').click();
    await page.waitForSelector('[role="dialog"]');
    report('Avec prefers-reduced-motion, le tiroir apparaît sans bouger', (await page.evaluate(() => document.getAnimations().length)) === 0);
    await context.close();
  }
} finally {
  await server.close();
}

// ---------------------------------------------------------------------------------------------
// Real site: production build, test feed with missing information, Content-Security-Policy

await build({ root, logLevel: 'error', build: { outDir: realOut, emptyOutDir: true } });
const previewServer = await preview({ root, logLevel: 'error', build: { outDir: realOut }, preview: { port: 4199, strictPort: false } });
const realBase = previewServer.resolvedUrls.local[0];

try {
  {
    const { context, page, errors } = await openPage(realBase, { waitFor: null });
    await page.waitForSelector('text=Impossible de charger les attaques pour le moment.');
    const demo = await page.evaluate(() => ({ line: document.querySelector('.demo-line') !== null, word: /fictive/i.test(document.body.innerText) }));
    report('Site réel sans data/cards.json : message, ni « Données fictives » ni liens de démo', !demo.line && !demo.word);
    report('Aucune autre erreur dans la console (site réel, sans données)', errors.filter((e) => !/404|Failed to load resource/.test(e)).length === 0);
    await context.close();
  }
  {
    // Test feed: the demo cards, with pieces of information removed as a real feed may have.
    const feed = buildDemoFeed(Date.now());
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
    await mkdir(path.join(realOut, 'data'), { recursive: true });
    await writeFile(path.join(realOut, 'data', 'cards.json'), JSON.stringify(feed));

    const { context, page, errors } = await openPage(realBase);
    await page.screenshot({ path: path.join(captures, 'reel-test-1440.png'), fullPage: true });
    const text = await page.evaluate(() => document.body.innerText);
    const csp = await page.evaluate(() => document.querySelector('meta[http-equiv="Content-Security-Policy"]')?.content ?? '');
    const articles = await page.locator('#attaques article, .brief__row').count();
    await page.locator('#lire-demo-telecomx').click();
    await page.waitForSelector('[role="dialog"]');
    const links = await page.$$eval('.sources a', (anchors) => anchors.map((a) => ({ href: a.href, rel: a.rel, target: a.target })));
    const mitre = await page.$$eval('.tech a', (anchors) => anchors.map((a) => a.href));
    await context.close();

    const phone = await openPage(realBase, { width: 390, height: 844 });
    await phone.page.screenshot({ path: path.join(captures, 'reel-test-390.png'), fullPage: true });
    await phone.context.close();

    report('Site réel avec un flux de test : toutes les attaques s’affichent', articles === 8, `${articles}`);
    report('Cartes incomplètes : « Non communiqué » à la place de chaque information manquante', (text.match(/Non communiqué/g) ?? []).length >= 5);
    report('Pays donné par une source : écrit en toutes lettres', text.includes('Groupe test (Pays test)'));
    report('Fiabilité absente du flux : traitée comme une rumeur, jamais comme confirmée', /Rumeur, non confirmée/.test(text));
    report('Liens des sources : seul le lien web reste, ouvert à part', links.length === 1 && links[0].href === 'https://example.org/article' && links[0].rel === 'noopener noreferrer' && links[0].target === '_blank', JSON.stringify(links));
    report('Techniques MITRE ATT&CK liées à attack.mitre.org', mitre.length > 0 && mitre.every((href) => href.startsWith('https://attack.mitre.org/techniques/')));
    report('Content-Security-Policy présente', csp.includes("connect-src 'self'"), csp);
    report('Aucune erreur dans la console, CSP comprise (site réel)', errors.length === 0, errors.join(' | '));
  }
} finally {
  await previewServer.close();
  await rm(realOut, { recursive: true, force: true });
}

report('Aucune requête vers un autre domaine', offsite.length === 0, [...new Set(offsite)].join(' '));
await browser.close();

const failed = results.filter((ok) => !ok).length;
console.log(`\n${results.length - failed}/${results.length} vérifications réussies. Captures : ${captures}`);
process.exitCode = failed === 0 ? 0 : 1;
