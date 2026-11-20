// The sentence under the date, of the form "<période> : <n> attaque(s) critique(s) et <n>
// grave(s). <n> concerne(nt) le grand public." Every number in it is counted on the cards on the
// page, and the period says exactly which ones: it is never written in advance.

import { LEVELS, SEVERITY } from './severity.js';

const NBSP = ' ';

const forPublic = (attack) => attack.audience !== 'entreprises';

/** Midnight, `daysBefore` days before `now`, in local time. */
function startOfDay(now, daysBefore = 0) {
  const day = new Date(now);
  day.setHours(0, 0, 0, 0);
  day.setDate(day.getDate() - daysBefore);
  return day;
}

/** "<n> attaque(s) critique(s) et <n> grave(s)", or "<n> significative(s) et <n> mineure(s)". */
function countPhrase(counts, levels, { noun }) {
  const parts = levels
    .filter((level) => counts[level] > 0)
    .map((level, index) => {
      const n = counts[level];
      const adjective = n > 1 ? SEVERITY[level].plural : SEVERITY[level].label.toLowerCase();
      const word = index === 0 && noun ? `${n > 1 ? 'attaques' : 'attaque'} ` : '';
      return `${n}${NBSP}${word}${adjective}`;
    });
  if (parts.length <= 1) return parts.join('');
  return `${parts.slice(0, -1).join(', ')} et ${parts[parts.length - 1]}`;
}

function publicPhrase(n) {
  if (n === 0) return 'Aucune ne concerne le grand public.';
  return `${n}${NBSP}${n > 1 ? 'concernent' : 'concerne'} le grand public.`;
}

/**
 * Summary of the cards shown (those of the last seven days). The period matches the dates of the
 * cards counted: "Aujourd’hui" when they are all from today, "Depuis hier" when some are from
 * yesterday, and "Ces sept derniers jours" when nothing happened since yesterday.
 */
export function digest(cards, now) {
  const sinceYesterday = cards.filter((card) => card.first_seen >= startOfDay(now, 1));
  let period = 'Ces sept derniers jours';
  let pool = cards;
  if (sinceYesterday.length > 0) {
    pool = sinceYesterday;
    period = sinceYesterday.every((card) => card.first_seen >= startOfDay(now)) ? 'Aujourd’hui' : 'Depuis hier';
  }

  if (pool.length === 0) return `${period}${NBSP}: aucune attaque.`;

  const counts = Object.fromEntries(LEVELS.map((level) => [level, pool.filter((card) => card.severity === level).length]));
  const serious = pool.filter((card) => card.severity === 'critique' || card.severity === 'grave');

  if (serious.length > 0) {
    const phrase = countPhrase(counts, ['critique', 'grave'], { noun: true });
    return `${period}${NBSP}: ${phrase}. ${publicPhrase(serious.filter(forPublic).length)}`;
  }
  const others = countPhrase(counts, ['significative', 'mineure'], { noun: false });
  return `${period}${NBSP}: aucune attaque critique ni grave, ${others}. ${publicPhrase(pool.filter(forPublic).length)}`;
}
