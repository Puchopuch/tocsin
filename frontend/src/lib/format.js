// Formatting helpers, in French and in English: dates, search, people and sources, safe links.
// They only shape what is displayed; they never change the data.

import { UI } from './i18n.js';
import { STATUS } from './severity.js';

const NBSP = ' ';

/**
 * Start of the window of cards shown: midnight, seven days ago. Whole days, as the collector
 * counts them, so that a source giving only a date counts the same way as one giving a time.
 */
export function windowStart(now) {
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() - 7);
  return start;
}

const FORMATS = {};

/** The date formats of a language, made once. */
function formats(lang) {
  if (!FORMATS[lang]) {
    const locale = UI[lang].locale;
    FORMATS[lang] = {
      dayMonth: new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short' }),
      dayMonthYear: new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', year: 'numeric' }),
      longDay: new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'long', year: 'numeric' }),
      weekday: new Intl.DateTimeFormat(locale, { weekday: 'long', day: 'numeric', month: 'long' }),
    };
  }
  return FORMATS[lang];
}

const WORDS = {
  fr: { today: 'aujourd’hui', yesterday: 'hier', at: 'à', on: 'le' },
  en: { today: 'today', yesterday: 'yesterday', at: 'at', on: 'on' },
};

const sameDay = (a, b) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

const isYesterday = (date, now) => {
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  return sameDay(date, yesterday);
};

/** "07 h 42" (padded, for cards) or "7 h 42" in French; "07:42" in English. */
export function clock(date, lang = 'fr', { pad = false } = {}) {
  const minutes = String(date.getMinutes()).padStart(2, '0');
  if (lang === 'en') return `${String(date.getHours()).padStart(2, '0')}:${minutes}`;
  const hours = String(date.getHours());
  return `${pad ? hours.padStart(2, '0') : hours}${NBSP}h${NBSP}${minutes}`;
}

const dayMonth = (date, now, lang) =>
  (date.getFullYear() === new Date(now).getFullYear() ? formats(lang).dayMonth : formats(lang).dayMonthYear).format(date);

// A date marked `dayOnly` (see hooks.js) came from a source that gives no time: no hour is ever
// shown for it, so that nothing is invented.

/** For the datetime attribute of <time>: the day alone when the source gave no time. */
export function machineDate(date) {
  if (!date.dayOnly) return date.toISOString();
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Short date of a card: the time today ("aujourd’hui" / "today" without a time), yesterday, or "18 nov." / "18 Nov". */
export function cardDate(date, now, lang = 'fr') {
  const words = WORDS[lang];
  if (sameDay(date, new Date(now))) return date.dayOnly ? words.today : clock(date, lang, { pad: true });
  if (isYesterday(date, now)) return words.yesterday;
  return dayMonth(date, now, lang);
}

/** After "Mis à jour" / "Updated": "à 7 h 42" / "at 07:42", "hier à …", "le 18 nov. à …". */
export function updatedAt(date, now, lang = 'fr') {
  const words = WORDS[lang];
  if (sameDay(date, new Date(now))) return `${words.at} ${clock(date, lang)}`;
  if (isYesterday(date, now)) return `${words.yesterday} ${words.at} ${clock(date, lang)}`;
  return `${words.on} ${dayMonth(date, now, lang)} ${words.at} ${clock(date, lang)}`;
}

/** "20 novembre 2026 à 7 h 42" / "20 November 2026 at 07:42", or the day alone. */
export function fullDate(date, lang = 'fr') {
  const day = formats(lang).longDay.format(date);
  return date.dayOnly ? day : `${day} ${WORDS[lang].at} ${clock(date, lang)}`;
}

/** "16 nov. à 14 h 10" / "16 Nov at 14:10", or the day alone, for the timeline. */
export function timelineDate(date, now, lang = 'fr') {
  const day = dayMonth(date, now, lang);
  return date.dayOnly ? day : `${day} ${WORDS[lang].at} ${clock(date, lang)}`;
}

/** "Vendredi 20 novembre" / "Friday 20 November". */
export const todayLabel = (now, lang = 'fr') => capitalize(formats(lang).weekday.format(now));

export const capitalize = (text) => text.charAt(0).toUpperCase() + text.slice(1);

// ---- Search ---------------------------------------------------------------------------------

/** Lower case, no accents, plain apostrophes, single spaces. */
export function fold(text) {
  return String(text ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[‘’]/g, "'")
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

const searchText = new WeakMap();

function haystack(attack) {
  let text = searchText.get(attack);
  if (text === undefined) {
    text = fold(
      [
        attack.title,
        attack.lede,
        attack.sector,
        attack.victim?.label,
        attack.attacker?.name,
        attack.attacker?.country,
        attack.method,
        attack.loot,
        attack.am_i_affected,
        attack.action,
        ...(attack.summary ?? []),
        ...(attack.technical?.cves ?? []),
        ...(attack.sources ?? []).map((source) => source.name),
      ]
        .filter(Boolean)
        .join(' '),
    );
    searchText.set(attack, text);
  }
  return text;
}

/** True when every word of the query appears in the attack, ignoring case and accents. */
export function matchesQuery(attack, query) {
  const words = fold(query).split(' ').filter(Boolean);
  if (words.length === 0) return true;
  const text = haystack(attack);
  return words.every((word) => text.includes(word));
}

// ---- People and sources ---------------------------------------------------------------------

/**
 * "Origine" / "Origin" of a card: the attacker's name (with the country when a reliable source
 * gives one), "Inconnue" / "Unknown" when nobody is known, "Non communiqué" / "Not disclosed" when
 * the feed says nothing; plus the status, only when it is not confirmed.
 */
export function origin(attacker, lang = 'fr') {
  const t = UI[lang];
  if (!attacker) return { value: t.notGiven, status: null };
  if (attacker.status === 'inconnu') return { value: t.unknownOrigin, status: null };
  const name = attacker.name || t.notGiven;
  const value = attacker.country ? `${name} (${attacker.country})` : name;
  const unconfirmed = STATUS[attacker.status]?.[lang].unconfirmed;
  return { value, status: unconfirmed ? `${unconfirmed}${attacker.source ? `, ${t.according(attacker.source)}` : ''}` : null };
}

/** "Cibles" / "Targets" of a card, with the status when only the attackers say so. */
export const targets = (victim, lang = 'fr') => ({
  value: victim?.label || UI[lang].notGiven,
  status: STATUS[victim?.status]?.[lang].unconfirmed ?? null,
});

/** Official sources first, the others in their original order. */
export const orderSources = (sources = []) =>
  [...sources].sort((a, b) => Number(b.official) - Number(a.official));

/** "Sources : CISA, NVD" in French, "Sources: CISA, NVD" in English; "Source" for one. */
export function sourcesLine(sources = [], lang = 'fr') {
  const t = UI[lang];
  const colon = lang === 'fr' ? `${NBSP}: ` : ': ';
  if (sources.length === 0) return `${t.sources}${colon}${t.notGiven.toLowerCase()}`;
  const names = [...new Set(orderSources(sources).map((source) => source.name))];
  return `${names.length > 1 ? t.sources : t.source}${colon}${names.join(', ')}`;
}

// ---- Links ----------------------------------------------------------------------------------

/** Page of a MITRE ATT&CK technique (T1199, T1566.002), or null if the id looks wrong. */
export function attackUrl(id) {
  const match = /^T(\d{4})(?:\.(\d{3}))?$/.exec(String(id ?? '').trim());
  if (!match) return null;
  return `https://attack.mitre.org/techniques/T${match[1]}/${match[2] ? `${match[2]}/` : ''}`;
}

const LABEL = '[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?';
const HOST = new RegExp(`^${LABEL}(?:\\.${LABEL})+$`);

/**
 * A link the page may show, checked again with the rules of the collector: https only, written in
 * plain ASCII without space, control character, backslash, quote or angle bracket, to a host name
 * without user name, password or port. Never javascript:, data:, vbscript:, file: or a link
 * without scheme (//), in capitals, encoded or after spaces; never a .onion address, an
 * internationalised (xn--) name or an IP address. Anything else gives null: the link is not shown.
 * The cases of collector/tests/data/links.json are checked on both sides.
 */
export function safeUrl(url) {
  if (typeof url !== 'string' || url.length > 2000 || !url.startsWith('https://')) return null;
  if (!/^[\x21-\x7e]+$/.test(url) || /[\\"<>`{}|^]/.test(url)) return null;
  const authority = url.slice('https://'.length).split(/[/?#]/, 1)[0];
  const host = authority.toLowerCase().replace(/\.$/, '');
  if (!HOST.test(host)) return null; // also refuses "@" (user, password), ":" (port), "%" and "["
  const labels = host.split('.');
  if (labels.at(-1) === 'onion' || /^\d+$/.test(labels.at(-1)) || labels.some((label) => label.startsWith('xn--'))) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' && parsed.hostname.replace(/\.$/, '') === host ? parsed.href : null;
  } catch {
    return null;
  }
}
