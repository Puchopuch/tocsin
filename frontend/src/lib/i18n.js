// Every text of the interface, in French and in English. The cards bring their own texts, written
// in both languages by the collector. French texts get French typography (typo.js); English texts
// do not.

import { typo } from './typo.js';

export const LANGS = ['fr', 'en'];
export const LANG_KEY = 'tocsin.lang';

/** Only "fr" or "en" is accepted, from storage or anywhere else; anything else gives null. */
export const validLang = (value) => (LANGS.includes(value) ? value : null);

/** The language of the browser: the first of French or English in its list, English otherwise. */
export function browserLang(languages) {
  for (const tag of languages ?? []) {
    const code = String(tag).slice(0, 2).toLowerCase();
    if (validLang(code)) return code;
  }
  return 'en';
}

const NBSP = ' ';

const FR = {
  locale: 'fr-FR',
  title: (name) => `${name}, les cyberattaques du jour`,
  skip: 'Aller aux attaques',
  attacks: 'Attaques',
  searchLabel: 'Rechercher une attaque',
  searchPlaceholder: 'Rechercher une attaque, une entreprise',
  loading: 'Chargement',
  unavailable: 'Données indisponibles',
  updated: 'Mis à jour',
  language: 'Langue',
  filterBySeverity: 'Filtrer par gravité',
  all: 'Toutes',
  publicOnly: 'Grand public uniquement',
  loadingAttacks: 'Chargement des attaques…',
  loadError: 'Impossible de charger les attaques pour le moment. Réessayez dans quelques minutes.',
  noAttack: 'Aucune attaque recensée pour le moment.',
  noMatch: 'Aucune attaque ne correspond à ces filtres.',
  showAll: 'Tout afficher',
  inBrief: 'En bref',
  footer: 'Chaque fiche cite ses sources. Les fiches de la CISA et du CERT-FR sont construites par des règles fixes ; celles de la presse sont rédigées par une IA à partir de faits vérifiés, et le disent.',
  aiNote: (role) => (role === 'traduction' ? 'Texte de la CISA traduit par une IA' : 'Rédigée par une IA à partir de l’article'),
  aiDetails: ({ role, model, prompts }) =>
    role === 'traduction'
      ? `Le texte de la CISA est traduit par une IA (${model}, consignes ${prompts}), sans rien ajouter ; le code vérifie qu’aucun chiffre ni lien n’apparaît en plus.`
      : `Fiche rédigée par une IA (${model}, consignes ${prompts}) à partir des seuls faits que l’article prouve par une citation ; le niveau, les liens et les statuts sont fixés par le code.`,
  methodLink: 'Méthode et sources',
  shown: (n) => (n === 0 ? 'Aucune attaque affichée' : `${n}${NBSP}${n > 1 ? 'attaques affichées' : 'attaque affichée'}`),
  origin: 'Origine',
  targets: 'Cibles',
  method: 'Méthode',
  impact: 'Impact',
  concern: 'Suis-je concerné ?',
  whatToDo: 'Que faire :',
  readMore: 'Lire la fiche',
  readMoreLabel: (title) => `Lire la fiche : ${title}`,
  read: 'Lire',
  readLabel: (title) => `Lire : ${title}`,
  notGiven: 'Non communiqué',
  unknownOrigin: 'Inconnue',
  source: 'Source',
  sources: 'Sources',
  rumour: (where) => (where ? `Rumeur vue sur ${where}, non confirmée` : 'Rumeur, non confirmée'),
  according: (who) => `selon ${who}`,
  close: 'Fermer',
  detected: 'Détectée le',
  stepsDone: (done, total) => `Étapes faites : ${done} sur ${total}`,
  happened: 'Ce qui s’est passé',
  why: 'Pourquoi ce niveau :',
  timeline: 'Chronologie',
  technical: 'Détails techniques',
  cves: 'Failles (CVE)',
  noCve: 'Aucune CVE publiée',
  software: 'Logiciels concernés',
  techniques: 'Techniques (MITRE ATT&CK)',
  officialSource: ', source officielle',
  openSource: 'Ouvrir la source',
  newTab: '(nouvel onglet)',
  noLink: 'Pas de lien',
  methodTitle: (name) => `Comment ${name} présente les attaques`,
  severityTitle: 'La gravité',
  claimsTitle: 'Les revendications et les rumeurs',
  statusesTitle: 'Les statuts',
  originsTitle: 'D’où viennent les informations',
  limitsTitle: 'Les limites',
  origins: [
    ['Autorités', 'CISA, l’agence américaine de cybersécurité (failles déjà exploitées), et CERT-FR (alertes).'],
    ['Revendications de pirates', 'ransomware.live, toujours affichées comme « Revendiqué, non confirmé ».'],
    ['Presse spécialisée', 'BleepingComputer, The Record, ZATAZ et LeMagIT, lus par une IA (Mistral) seulement quand une clé est fournie : chaque fait doit être cité mot pour mot dans l’article, et le code fixe le niveau, les liens et les statuts.'],
  ],
  limits: [
    'Les fiches sont construites automatiquement à partir des sources citées : si une source se trompe, la fiche aussi.',
    "L'origine d'une attaque n'est donnée que si une source fiable la donne.",
    'Une information absente est marquée « Non communiqué » plutôt que devinée.',
    "Aucune donnée personnelle : une revendication dont la victime pourrait être une personne n'est pas publiée.",
    'Aucun lien vers les sites des rançonneurs ni vers des données volées.',
    'Une fiche rédigée ou traduite par une IA le dit sur la fiche elle-même.',
    "Les données sont mises à jour à chaque collecte, dont l'heure est affichée en haut de la page : ce n'est pas du direct.",
  ],
};

const EN = {
  locale: 'en-GB',
  title: (name) => `${name}, today’s cyberattacks`,
  skip: 'Skip to the attacks',
  attacks: 'Attacks',
  searchLabel: 'Search for an attack',
  searchPlaceholder: 'Search for an attack, a company',
  loading: 'Loading',
  unavailable: 'Data unavailable',
  updated: 'Updated',
  language: 'Language',
  filterBySeverity: 'Filter by severity',
  all: 'All',
  publicOnly: 'General public only',
  loadingAttacks: 'Loading attacks…',
  loadError: 'The attacks cannot be loaded right now. Try again in a few minutes.',
  noAttack: 'No attack recorded at the moment.',
  noMatch: 'No attack matches these filters.',
  showAll: 'Show all',
  inBrief: 'In brief',
  footer: 'Every card cites its sources. CISA and CERT-FR cards are built by fixed rules; press cards are written by an AI from checked facts, and say so.',
  aiNote: (role) => (role === 'traduction' ? 'CISA text translated by an AI' : 'Written by an AI from the article'),
  aiDetails: ({ role, model, prompts }) =>
    role === 'traduction'
      ? `The CISA text is translated by an AI (${model}, prompts ${prompts}), adding nothing; the code checks that no number or link appears in addition.`
      : `Card written by an AI (${model}, prompts ${prompts}) from the facts the article proves with a quote, and nothing else; the level, links and statuses are set by the code.`,
  methodLink: 'Method and sources',
  shown: (n) => (n === 0 ? 'No attack shown' : `${n} ${n > 1 ? 'attacks shown' : 'attack shown'}`),
  origin: 'Origin',
  targets: 'Targets',
  method: 'Method',
  impact: 'Impact',
  concern: 'Am I affected?',
  whatToDo: 'What to do:',
  readMore: 'Read more',
  readMoreLabel: (title) => `Read more: ${title}`,
  read: 'Read',
  readLabel: (title) => `Read: ${title}`,
  notGiven: 'Not disclosed',
  unknownOrigin: 'Unknown',
  source: 'Source',
  sources: 'Sources',
  rumour: (where) => (where ? `Rumour seen on ${where}, not confirmed` : 'Rumour, not confirmed'),
  according: (who) => `according to ${who}`,
  close: 'Close',
  detected: 'Detected on',
  stepsDone: (done, total) => `Steps done: ${done} of ${total}`,
  happened: 'What happened',
  why: 'Why this level:',
  timeline: 'Timeline',
  technical: 'Technical details',
  cves: 'Flaws (CVE)',
  noCve: 'No CVE published',
  software: 'Software concerned',
  techniques: 'Techniques (MITRE ATT&CK)',
  officialSource: ', official source',
  openSource: 'Open the source',
  newTab: '(new tab)',
  noLink: 'No link',
  methodTitle: (name) => `How ${name} presents attacks`,
  severityTitle: 'Severity',
  claimsTitle: 'Claims and rumours',
  statusesTitle: 'Statuses',
  originsTitle: 'Where the information comes from',
  limitsTitle: 'Limits',
  origins: [
    ['Authorities', 'CISA, the US cybersecurity agency (flaws already exploited), and CERT-FR, the French government’s computer emergency team (alerts).'],
    ['Claims by attackers', 'ransomware.live, always shown as “Claimed, not confirmed”.'],
    ['Specialised press', 'BleepingComputer, The Record, ZATAZ and LeMagIT, read by an AI (Mistral) only when a key is given: each fact must be quoted word for word from the article, and the code sets the level, links and statuses.'],
  ],
  limits: [
    'The cards are built automatically from the sources cited: if a source is wrong, so is the card.',
    'The origin of an attack is given only when a reliable source gives it.',
    'Missing information is marked “Not disclosed” rather than guessed.',
    'No personal data: a claim whose victim could be a person is not published.',
    'No link to extortionists’ sites or to stolen data.',
    'A card written or translated by an AI says so on the card itself.',
    'The data is updated at each collection, whose time is shown at the top of the page: this is not live.',
  ],
};

/** French typography on every French text, functions included. */
function french(dictionary) {
  const out = {};
  for (const [key, value] of Object.entries(dictionary)) {
    if (key === 'locale') out[key] = value;
    else if (typeof value === 'function') out[key] = (...args) => typo(value(...args));
    else if (Array.isArray(value)) out[key] = value.map((item) => (Array.isArray(item) ? item.map(typo) : typo(item)));
    else out[key] = typo(value);
  }
  return out;
}

export const UI = { fr: french(FR), en: EN };
