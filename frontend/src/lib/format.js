// Formatting helpers: dates the French way, search, people and sources, safe links.
// They only shape what is displayed; they never change the data.

import { STATUS } from './severity.js';

const DAY = 24 * 60 * 60 * 1000;
const NBSP = ' ';

/** Alerts older than this are not shown. */
export const WEEK = 7 * DAY;

/** What a card shows when a piece of information is missing: the line stays. */
export const NOT_GIVEN = 'Non communiqué';

const DAY_MONTH = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' });
const DAY_MONTH_YEAR = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' });
const LONG_DAY = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });
const WEEKDAY = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });

const sameDay = (a, b) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

const isYesterday = (date, now) => {
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  return sameDay(date, yesterday);
};

/** "07 h 42" (padded, for cards) or "7 h 42" (for sentences). */
export function clock(date, { pad = false } = {}) {
  const hours = String(date.getHours());
  return `${pad ? hours.padStart(2, '0') : hours}${NBSP}h${NBSP}${String(date.getMinutes()).padStart(2, '0')}`;
}

const dayMonth = (date, now) =>
  (date.getFullYear() === new Date(now).getFullYear() ? DAY_MONTH : DAY_MONTH_YEAR).format(date);

/** Short date of a card: "07 h 42" today, "hier", or "18 nov.". */
export function cardDate(date, now) {
  if (sameDay(date, new Date(now))) return clock(date, { pad: true });
  if (isYesterday(date, now)) return 'hier';
  return dayMonth(date, now);
}

/** "à 7 h 42", "hier à 23 h 10" or "le 18 nov. à 7 h 42", after "Mis à jour". */
export function updatedAt(date, now) {
  if (sameDay(date, new Date(now))) return `à ${clock(date)}`;
  if (isYesterday(date, now)) return `hier à ${clock(date)}`;
  return `le ${dayMonth(date, now)} à ${clock(date)}`;
}

/** "20 novembre 2026 à 7 h 42". */
export const fullDate = (date) => `${LONG_DAY.format(date)} à ${clock(date)}`;

/** "16 nov. à 14 h 10", for the timeline. */
export const timelineDate = (date, now) => `${dayMonth(date, now)} à ${clock(date)}`;

/** "Vendredi 20 novembre". */
export const todayLabel = (now) => capitalize(WEEKDAY.format(now));

/** "1 attaque", "2 attaques". In French, 0 and 1 take the singular. */
export const plural = (count, one, many) => `${count}${NBSP}${count > 1 ? many : one}`;

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
 * "Origine" of a card: the attacker's name (with the country when a reliable source gives one),
 * "Inconnue" when nobody is known, "Non communiqué" when the feed says nothing; plus the
 * status, only when it is not confirmed.
 */
export function origin(attacker) {
  if (!attacker) return { value: NOT_GIVEN, status: null };
  if (attacker.status === 'inconnu') return { value: 'Inconnue', status: null };
  const name = attacker.name || NOT_GIVEN;
  const value = attacker.country ? `${name} (${attacker.country})` : name;
  const unconfirmed = STATUS[attacker.status]?.unconfirmed;
  return { value, status: unconfirmed ? `${unconfirmed}${attacker.source ? `, selon ${attacker.source}` : ''}` : null };
}

/** "Cibles" of a card, with "Revendiqué, non confirmé" when only the attackers say so. */
export const targets = (victim) => ({
  value: victim?.label || NOT_GIVEN,
  status: STATUS[victim?.status]?.unconfirmed ?? null,
});

/** Official sources first, the others in their original order. */
export const orderSources = (sources = []) =>
  [...sources].sort((a, b) => Number(b.official) - Number(a.official));

/** "Sources : CERT-FR, LeMagIT", or "Source : TelecomX". */
export function sourcesLine(sources = []) {
  if (sources.length === 0) return `Sources${NBSP}: ${NOT_GIVEN.toLowerCase()}`;
  const names = [...new Set(orderSources(sources).map((source) => source.name))];
  return `${names.length > 1 ? 'Sources' : 'Source'}${NBSP}: ${names.join(', ')}`;
}

// ---- Links ----------------------------------------------------------------------------------

/** Page of a MITRE ATT&CK technique (T1199, T1566.002), or null if the id looks wrong. */
export function attackUrl(id) {
  const match = /^T(\d{4})(?:\.(\d{3}))?$/.exec(String(id ?? '').trim());
  if (!match) return null;
  return `https://attack.mitre.org/techniques/T${match[1]}/${match[2] ? `${match[2]}/` : ''}`;
}

/** Only plain web links are kept; never javascript:, data: or .onion addresses. */
export function safeUrl(url) {
  if (typeof url !== 'string' || url === '') return null;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') return null;
    if (parsed.hostname.endsWith('.onion')) return null;
    return parsed.href;
  } catch {
    return null;
  }
}
