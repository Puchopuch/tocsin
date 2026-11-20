// The sentence under the date, in French or in English. Every number in it is counted on the cards
// on the page, and the period says exactly which ones: it is never written in advance.
//   French:  "<période> : <n> attaque(s) critique(s) et <n> grave(s). <n> concerne(nt) le grand public."
//   English: "<period>: <n> critical and <n> severe attack(s). <n> affect(s) the general public."

import { LEVEL_NAMES, LEVELS } from './severity.js';

const NBSP = ' ';

const forPublic = (attack) => attack.audience !== 'entreprises';

/** Midnight, `daysBefore` days before `now`, in local time. */
function startOfDay(now, daysBefore = 0) {
  const day = new Date(now);
  day.setHours(0, 0, 0, 0);
  day.setDate(day.getDate() - daysBefore);
  return day;
}

/** "a, b et c" / "a, b and c". */
function joined(parts, and) {
  if (parts.length <= 1) return parts.join('');
  return `${parts.slice(0, -1).join(', ')} ${and} ${parts[parts.length - 1]}`;
}

const PERIODS = {
  fr: { today: 'Aujourd’hui', yesterday: 'Depuis hier', week: 'Ces sept derniers jours' },
  en: { today: 'Today', yesterday: 'Since yesterday', week: 'Over the last seven days' },
};

const PHRASES = {
  fr: {
    colon: `${NBSP}: `,
    counts(counts, levels, noun) {
      const parts = levels
        .filter((level) => counts[level] > 0)
        .map((level, index) => {
          const n = counts[level];
          const name = LEVEL_NAMES.fr[level];
          const adjective = n > 1 ? name.plural : name.label.toLowerCase();
          const word = index === 0 && noun ? `${n > 1 ? 'attaques' : 'attaque'} ` : '';
          return `${n}${NBSP}${word}${adjective}`;
        });
      return joined(parts, 'et');
    },
    none: 'aucune attaque.',
    calm: (others) => `aucune attaque critique ni grave, ${others}.`,
    public: (n) => (n === 0 ? 'Aucune ne concerne le grand public.' : `${n}${NBSP}${n > 1 ? 'concernent' : 'concerne'} le grand public.`),
  },
  en: {
    colon: ': ',
    counts(counts, levels, noun) {
      const present = levels.filter((level) => counts[level] > 0);
      const parts = present.map((level) => `${counts[level]} ${LEVEL_NAMES.en[level].plural}`);
      const total = present.reduce((sum, level) => sum + counts[level], 0);
      return `${joined(parts, 'and')}${noun ? ` ${total > 1 ? 'attacks' : 'attack'}` : ''}`;
    },
    none: 'no attack.',
    calm: (others) => `no critical or severe attack, ${others}.`,
    public: (n) => (n === 0 ? 'None affects the general public.' : `${n} ${n > 1 ? 'affect' : 'affects'} the general public.`),
  },
};

/**
 * Summary of the cards shown (those of the last seven days). The period matches the dates of the
 * cards counted: today when they are all from today, since yesterday when some are from
 * yesterday, and the last seven days when nothing happened since yesterday.
 */
export function digest(cards, now, lang = 'fr') {
  const phrases = PHRASES[lang];
  const periods = PERIODS[lang];
  const sinceYesterday = cards.filter((card) => card.first_seen >= startOfDay(now, 1));
  let period = periods.week;
  let pool = cards;
  if (sinceYesterday.length > 0) {
    pool = sinceYesterday;
    period = sinceYesterday.every((card) => card.first_seen >= startOfDay(now)) ? periods.today : periods.yesterday;
  }

  if (pool.length === 0) return `${period}${phrases.colon}${phrases.none}`;

  const counts = Object.fromEntries(LEVELS.map((level) => [level, pool.filter((card) => card.severity === level).length]));
  const serious = pool.filter((card) => card.severity === 'critique' || card.severity === 'grave');

  if (serious.length > 0) {
    const phrase = phrases.counts(counts, ['critique', 'grave'], true);
    return `${period}${phrases.colon}${phrase}. ${phrases.public(serious.filter(forPublic).length)}`;
  }
  const others = phrases.counts(counts, ['significative', 'mineure'], false);
  return `${period}${phrases.colon}${phrases.calm(others)} ${phrases.public(pool.filter(forPublic).length)}`;
}
