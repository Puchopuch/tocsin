// The sentence under the date, in French or in English. Every number in it is counted on the cards
// on the page, and the period says exactly which ones: it is never written in advance.
//   French:  "<période> : <n> alerte(s) critique(s) et <n> grave(s). <n> concerne(nt) le grand public."
//   English: "<period>: <n> critical and <n> severe alert(s). <n> affect(s) the general public."
// "attaques" / "attacks" only when every card counted is an attack; as soon as a flaw is counted,
// "alertes" / "alerts", which covers both.

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

// [singular, plural] of the noun, by language and kind of cards counted.
const NOUNS = {
  fr: { attaque: ['attaque', 'attaques'], alerte: ['alerte', 'alertes'] },
  en: { attaque: ['attack', 'attacks'], alerte: ['alert', 'alerts'] },
};
const kindOf = (cards) => (cards.every((card) => card.kind === 'attaque') ? 'attaque' : 'alerte');

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
          const word = index === 0 && noun ? `${n > 1 ? noun[1] : noun[0]} ` : '';
          return `${n}${NBSP}${word}${adjective}`;
        });
      return joined(parts, 'et');
    },
    none: (noun) => `aucune ${noun[0]}.`,
    calm: (others, noun) => `aucune ${noun[0]} critique ni grave, ${others}.`,
    public: (n) => (n === 0 ? 'Aucune ne concerne le grand public.' : `${n}${NBSP}${n > 1 ? 'concernent' : 'concerne'} le grand public.`),
  },
  en: {
    colon: ': ',
    counts(counts, levels, noun) {
      const present = levels.filter((level) => counts[level] > 0);
      const parts = present.map((level) => `${counts[level]} ${LEVEL_NAMES.en[level].plural}`);
      const total = present.reduce((sum, level) => sum + counts[level], 0);
      return `${joined(parts, 'and')}${noun ? ` ${total > 1 ? noun[1] : noun[0]}` : ''}`;
    },
    none: (noun) => `no ${noun[0]}.`,
    calm: (others, noun) => `no critical or severe ${noun[0]}, ${others}.`,
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

  const nouns = NOUNS[lang];
  if (pool.length === 0) return `${period}${phrases.colon}${phrases.none(nouns.attaque)}`;

  const counts = Object.fromEntries(LEVELS.map((level) => [level, pool.filter((card) => card.severity === level).length]));
  const serious = pool.filter((card) => card.severity === 'critique' || card.severity === 'grave');

  if (serious.length > 0) {
    const phrase = phrases.counts(counts, ['critique', 'grave'], nouns[kindOf(serious)]);
    return `${period}${phrases.colon}${phrase}. ${phrases.public(serious.filter(forPublic).length)}`;
  }
  const others = phrases.counts(counts, ['significative', 'mineure'], null);
  return `${period}${phrases.colon}${phrases.calm(others, nouns[kindOf(pool)])} ${phrases.public(pool.filter(forPublic).length)}`;
}
