// Severity levels, statuses and the severity grid, in French and in English.
//
// Severity reads like a weather warning: a 10px square in the level's colour, the word itself
// always in black. The pale yellow square gets a dark outline so that it stays visible on white.

import { typo } from './typo.js';

export const LEVELS = ['critique', 'grave', 'significative', 'mineure'];

export const SEVERITY = {
  critique: { square: '#C1121F' },
  grave: { square: '#E8590C' },
  significative: { square: '#F5C400', edge: '#8A6D00' },
  mineure: { square: '#8A8A8A' },
};

/** The name of each level, alone and in the plural, as the daily sentence uses it. */
export const LEVEL_NAMES = {
  fr: {
    critique: { label: 'Critique', plural: 'critiques' },
    grave: { label: 'Grave', plural: 'graves' },
    significative: { label: 'Significative', plural: 'significatives' },
    mineure: { label: 'Mineure', plural: 'mineures' },
  },
  en: {
    critique: { label: 'Critical', plural: 'critical' },
    grave: { label: 'Severe', plural: 'severe' },
    significative: { label: 'Significant', plural: 'significant' },
    mineure: { label: 'Minor', plural: 'minor' },
  },
};

// How sure we are about the attacker and the victim. `unconfirmed` is what the cards show next
// to the information; nothing is shown when it is confirmed.
export const STATUS = {
  confirme: {
    fr: { label: 'Confirmé', unconfirmed: null, meaning: typo("Une source fiable l'établit : autorité, victime ou enquête publiée.") },
    en: { label: 'Confirmed', unconfirmed: null, meaning: 'A reliable source establishes it: an authority, the victim or a published investigation.' },
  },
  revendique: {
    fr: { label: 'Revendiqué', unconfirmed: 'Revendiqué, non confirmé', meaning: typo("Seuls les pirates l'affirment, souvent pour faire pression. Rien n'est vérifié.") },
    en: { label: 'Claimed', unconfirmed: 'Claimed, not confirmed', meaning: 'Only the attackers say so, often to put pressure. Nothing is verified.' },
  },
  presume: {
    fr: { label: 'Présumé', unconfirmed: 'Présumé, non confirmé', meaning: typo("Une source fiable l'avance, sans preuve publique définitive.") },
    en: { label: 'Suspected', unconfirmed: 'Suspected, not confirmed', meaning: 'A reliable source puts it forward, without final public proof.' },
  },
  inconnu: {
    fr: { label: 'Inconnu', unconfirmed: null, meaning: typo("Aucune source fiable ne permet de l'établir pour l'instant.") },
    en: { label: 'Unknown', unconfirmed: null, meaning: 'No reliable source can establish it yet.' },
  },
};

export const GRID_INTRO = {
  fr: typo("Une attaque prend le niveau le plus élevé atteint par l'un de ses critères."),
  en: 'An attack takes the highest level reached by one of its criteria.',
};

export const GRID = {
  fr: [
    {
      level: 'critique',
      criteria: typo('Des millions de personnes avec des données sensibles, des services vitaux touchés (hôpitaux, énergie, eau, transports), un impact national, ou une attaque en masse, par exemple un fournisseur piraté pour attaquer ses clients.'),
    },
    {
      level: 'grave',
      criteria: typo("Plus de 100 000 personnes, des données sensibles (santé, banque, identité), une paralysie de plus d'une semaine, un service public paralysé, une faille déjà exploitée dans un logiciel répandu, ou une alerte du CERT-FR."),
    },
    {
      level: 'significative',
      criteria: typo("De 1 000 à 100 000 personnes, une organisation paralysée moins d'une semaine, une grande entreprise touchée sans fuite importante, ou une faille déjà exploitée dans un logiciel peu répandu."),
    },
    { level: 'mineure', criteria: typo('Moins de 1 000 personnes, une panne de quelques heures, une seule petite structure.') },
  ],
  en: [
    {
      level: 'critique',
      criteria: 'Millions of people with sensitive data, vital services hit (hospitals, energy, water, transport), a national impact, or a mass attack, for example a supplier hacked to attack its customers.',
    },
    {
      level: 'grave',
      criteria: 'More than 100,000 people, sensitive data (health, banking, identity), a paralysis of more than a week, a paralysed public service, a flaw already exploited in widespread software, or a CERT-FR alert.',
    },
    {
      level: 'significative',
      criteria: 'From 1,000 to 100,000 people, an organisation paralysed for less than a week, a large company hit without a major leak, or a flaw already exploited in less common software.',
    },
    { level: 'mineure', criteria: 'Fewer than 1,000 people, an outage of a few hours, a single small organisation.' },
  ],
};

export const CLAIM_RULE = {
  fr: typo("Tant qu'aucune source fiable ne confirme une attaque revendiquée par des pirates, ou une rumeur, elle reste au plus « Significative ». Sinon, on ferait la publicité des rançonneurs."),
  en: 'As long as no reliable source confirms an attack claimed by attackers, or a rumour, it stays at most “Significant”. Otherwise, we would be advertising the extortionists.',
};

const CAPPED = {
  fr: typo("Non confirmée : « Significative » au plus, tant qu'aucune source fiable ne la confirme."),
  en: 'Not confirmed: “Significant” at most, until a reliable source confirms it.',
};

/**
 * Safety net: an attack only claimed, or only a rumour, is never shown above "significative",
 * whatever the feed says.
 */
export function applyClaimRule(attack, lang = 'fr') {
  const unconfirmed = attack.victim.status === 'revendique' || attack.reliability === 'rumeur';
  if (!unconfirmed || LEVELS.indexOf(attack.severity) >= 2) return attack;
  return { ...attack, severity: 'significative', severity_reason: CAPPED[lang] };
}
