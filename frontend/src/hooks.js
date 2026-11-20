// Data and state hooks. The site reads data/cards.json, written by the collector at each
// collection (collector/ at the root of the repository), and nothing else. There is no other
// mode: without that file, the page says that no attack has been recorded yet.

import { useCallback, useEffect, useState } from 'react';
import { applyClaimRule, LEVELS, STATUS } from './lib/severity.js';
import { safeUrl } from './lib/format.js';
import { typo } from './lib/typo.js';

const env = import.meta.env ?? {};

const FEED_URL = `${env.BASE_URL ?? '/'}data/cards.json`;
const AUDIENCES = ['grand_public', 'entreprises', 'les_deux'];
/** The file is read again every 5 minutes, and whenever the tab comes back into view. */
const REFRESH = 5 * 60_000;
const DAY_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

/**
 * A Date, or null. A day alone ("2026-11-18"), given by a source without a time, is that day in
 * local time, marked `dayOnly` so that no hour is ever shown for it.
 */
function toDate(value) {
  const day = typeof value === 'string' ? DAY_ONLY.exec(value) : null;
  if (day) {
    const date = new Date(Number(day[1]), Number(day[2]) - 1, Number(day[3]));
    if (Number.isNaN(date.getTime())) return null;
    date.dayOnly = true;
    return date;
  }
  const date = new Date(value);
  return value && !Number.isNaN(date.getTime()) ? date : null;
}

const list = (value) => (Array.isArray(value) ? value : []);
const text = (value) => (typeof value === 'string' ? typo(value.trim()) : '');
const firstSentence = (paragraph) => /^.*?[.!?](?=\s|$)/.exec(paragraph ?? '')?.[0] ?? paragraph ?? '';

/** The attacker as given by the feed; null when the feed says nothing about it. */
function attackerOf(raw) {
  if (!raw || typeof raw !== 'object') return null;
  const name = text(raw.name);
  // A name without a status is never shown as confirmed.
  const fallback = name ? 'presume' : 'inconnu';
  return {
    name,
    country: text(raw.country) || null,
    status: STATUS[raw.status] ? raw.status : fallback,
    source: text(raw.source) || null,
  };
}

/** One alert of the feed, with Date objects and safe defaults; null if it cannot be shown. */
export function normalizeAttack(raw) {
  const firstSeen = toDate(raw?.first_seen);
  if (!raw?.id || !text(raw.title) || !LEVELS.includes(raw.severity) || !firstSeen) return null;
  const summary = list(raw.summary).map(text).filter(Boolean);

  return applyClaimRule({
    id: String(raw.id),
    severity: raw.severity,
    severity_reason: text(raw.severity_reason),
    title: text(raw.title),
    lede: text(raw.lede) || firstSentence(summary[0]),
    first_seen: firstSeen,
    // True only when a source confirms that the flaw is already exploited.
    exploited: raw.exploited === true,
    sector: text(raw.sector),
    audience: AUDIENCES.includes(raw.audience) ? raw.audience : 'les_deux',
    // Only "confirme" counts as confirmed: anything else is treated as a rumour.
    reliability: raw.reliability === 'confirme' ? 'confirme' : 'rumeur',
    reliability_source: text(raw.reliability_source) || null,
    attacker: attackerOf(raw.attacker),
    victim: {
      label: text(raw.victim?.label),
      status: STATUS[raw.victim?.status] ? raw.victim.status : 'inconnu',
    },
    method: text(raw.method),
    loot: text(raw.loot),
    am_i_affected: text(raw.am_i_affected),
    action: text(raw.action),
    summary,
    timeline: list(raw.timeline)
      .map((event) => ({ date: toDate(event?.date), label: text(event?.label) }))
      .filter((event) => event.date && event.label),
    protection_steps: list(raw.protection_steps).map(text).filter(Boolean),
    technical: {
      cves: list(raw.technical?.cves).filter((cve) => typeof cve === 'string'),
      software: list(raw.technical?.software).map(text).filter(Boolean),
      techniques: list(raw.technical?.techniques)
        .filter((technique) => technique?.id)
        .map((technique) => ({ id: String(technique.id), name: text(technique.name) })),
    },
    sources: list(raw.sources)
      .filter((source) => source?.name)
      .map((source) => ({
        name: text(source.name),
        title: text(source.title),
        url: safeUrl(source.url),
        official: source.official === true,
      })),
  });
}

/** The whole feed: { generatedAt, attacks }. Throws if the file is not a feed. */
export function normalizeFeed(json) {
  const generatedAt = toDate(json?.generated_at);
  if (!generatedAt || !Array.isArray(json?.attacks)) throw new Error('Invalid feed');
  return { generatedAt, attacks: json.attacks.map(normalizeAttack).filter(Boolean) };
}

const EMPTY = { status: 'empty', generatedAt: null, attacks: [] };

/** The feed, or EMPTY when no collection has written it yet. Throws when it cannot be read. */
async function loadFeed(signal) {
  const response = await fetch(FEED_URL, { cache: 'no-cache', signal });
  const type = response.headers.get('content-type') ?? '';
  // No file yet: a 404, or the HTML page that some servers send in its place.
  if (response.status === 404 || (response.ok && type.includes('text/html'))) return EMPTY;
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return { status: 'ready', ...normalizeFeed(await response.json()) };
}

const sameFeed = (a, b) => a.status === b.status && a.generatedAt?.getTime() === b.generatedAt?.getTime();

/**
 * The attacks to show. `status` is "loading", "ready" (the file was read; it may hold no attack),
 * "empty" (no file: no collection yet) or "error" (the file cannot be read). After the first
 * load, a refresh that fails keeps what is shown.
 */
export function useAttacks() {
  const [state, setState] = useState({ status: 'loading', generatedAt: null, attacks: [] });

  useEffect(() => {
    let controller = null;
    async function refresh() {
      controller?.abort();
      controller = new AbortController();
      try {
        const next = await loadFeed(controller.signal);
        setState((current) => (sameFeed(current, next) ? current : next));
      } catch (error) {
        if (error.name === 'AbortError') return;
        setState((current) => (current.status === 'loading' ? { status: 'error', generatedAt: null, attacks: [] } : current));
      }
    }
    const onVisible = () => {
      if (document.visibilityState === 'visible') refresh();
    };
    refresh();
    const timer = setInterval(refresh, REFRESH);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisible);
      controller?.abort();
    };
  }, []);

  return state;
}

/** Current time in milliseconds, refreshed every minute and when the tab becomes visible. */
export function useNow(interval = 60_000) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const tick = () => setNow(Date.now());
    const onVisibility = () => {
      if (document.visibilityState === 'visible') tick();
    };
    const timer = setInterval(tick, interval);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [interval]);

  return now;
}

/**
 * A value kept in this browser only (localStorage): the ticks of the "Que faire" steps. Works
 * without storage too (private mode, blocked site data).
 */
export function useStored(key, fallback) {
  const [value, setValue] = useState(() => {
    try {
      const saved = window.localStorage.getItem(key);
      return saved === null ? fallback : JSON.parse(saved);
    } catch {
      return fallback;
    }
  });

  const update = useCallback(
    (next) => {
      setValue((current) => {
        const resolved = typeof next === 'function' ? next(current) : next;
        try {
          window.localStorage.setItem(key, JSON.stringify(resolved));
        } catch {
          // Storage unavailable: keep the value for this visit only.
        }
        return resolved;
      });
    },
    [key],
  );

  return [value, update];
}
