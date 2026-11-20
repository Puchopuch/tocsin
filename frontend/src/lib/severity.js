// Severity levels, statuses and the severity grid.
//
// Severity reads like a weather warning: a 10px square in the level's colour, the word itself
// always in black. The pale yellow square gets a dark outline so that it stays visible on white.

import { typo } from './typo.js';

export const LEVELS = ['critique', 'grave', 'significative', 'mineure'];

export const SEVERITY = {
  critique: { label: 'Critique', plural: 'critiques', square: '#C1121F' },
  grave: { label: 'Grave', plural: 'graves', square: '#E8590C' },
  significative: { label: 'Significative', plural: 'significatives', square: '#F5C400', edge: '#8A6D00' },
  mineure: { label: 'Mineure', plural: 'mineures', square: '#8A8A8A' },
};

// How sure we are about the attacker and the victim. `unconfirmed` is what the cards show next
// to the information; nothing is shown when it is confirmed.
export const STATUS = {
  confirme: {
    label: 'Confirmé',
    unconfirmed: null,
    meaning: typo("Une source fiable l'établit : autorité, victime ou enquête publiée."),
  },
  revendique: {
    label: 'Revendiqué',
    unconfirmed: 'Revendiqué, non confirmé',
    meaning: typo("Seuls les pirates l'affirment, souvent pour faire pression. Rien n'est vérifié."),
  },
  presume: {
    label: 'Présumé',
    unconfirmed: 'Présumé, non confirmé',
    meaning: typo("Une source fiable l'avance, sans preuve publique définitive."),
  },
  inconnu: {
    label: 'Inconnu',
    unconfirmed: null,
    meaning: typo("Aucune source fiable ne permet de l'établir pour l'instant."),
  },
};

export const GRID_INTRO = typo("Une attaque prend le niveau le plus élevé atteint par l'un de ses critères.");

export const GRID = [
  {
    level: 'critique',
    criteria: typo(
      'Des millions de personnes avec des données sensibles, des services vitaux touchés (hôpitaux, énergie, eau, transports), un impact national, ou une attaque en masse, par exemple un fournisseur piraté pour attaquer ses clients.',
    ),
  },
  {
    level: 'grave',
    criteria: typo(
      "Plus de 100 000 personnes, des données sensibles (santé, banque, identité), une paralysie de plus d'une semaine, un service public paralysé, ou une faille déjà exploitée dans un logiciel répandu.",
    ),
  },
  {
    level: 'significative',
    criteria: typo(
      "De 1 000 à 100 000 personnes, une organisation paralysée moins d'une semaine, ou une grande entreprise touchée sans fuite importante.",
    ),
  },
  {
    level: 'mineure',
    criteria: typo('Moins de 1 000 personnes, une panne de quelques heures, une seule petite structure.'),
  },
];

export const CLAIM_RULE = typo(
  "Tant qu'aucune source fiable ne confirme une attaque revendiquée par des pirates, ou une rumeur, elle reste au plus « Significative ». Sinon, on ferait la publicité des rançonneurs.",
);

/**
 * Safety net: an attack only claimed, or only a rumour, is never shown above "significative",
 * whatever the feed says.
 */
export function applyClaimRule(attack) {
  const unconfirmed = attack.victim.status === 'revendique' || attack.reliability === 'rumeur';
  if (!unconfirmed || LEVELS.indexOf(attack.severity) >= 2) return attack;
  return {
    ...attack,
    severity: 'significative',
    severity_reason: typo("Non confirmée : « Significative » au plus, tant qu'aucune source fiable ne la confirme."),
  };
}
