// Data and state hooks. The site is static: in demo mode it shows the fictional alerts of
// data/demo.js; otherwise it reads data/cards.json, rebuilt every hour by the pipeline, and
// nothing else. The real site never falls back on demo data.

import { useCallback, useEffect, useRef, useState } from 'react';
import { buildDemoFeed, buildSimulatedAlert } from './data/demo.js';
import { applyClaimRule, LEVELS, STATUS } from './lib/severity.js';
import { safeUrl } from './lib/format.js';
import { typo } from './lib/typo.js';

const env = import.meta.env ?? {};

export const IS_DEMO = env.VITE_DEMO === 'true';
const FEED_URL = `${env.BASE_URL ?? '/'}data/cards.json`;
const AUDIENCES = ['grand_public', 'entreprises', 'les_deux'];

const toDate = (value) => {
  const date = new Date(value);
  return value && !Number.isNaN(date.getTime()) ? date : null;
};
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

const demoState = (calm) => ({ status: 'ready', ...normalizeFeed(buildDemoFeed(Date.now(), { calm })) });

/**
 * The alerts to show. `status` is "loading", "ready" or "error". In demo mode, `calm` swaps in a
 * calm day, and `simulate()` puts a new critical alert first and returns it.
 */
export function useAttacks({ calm = false } = {}) {
  const [state, setState] = useState(() =>
    IS_DEMO ? demoState(calm) : { status: 'loading', generatedAt: null, attacks: [] },
  );
  const simulated = useRef(0);
  const [shownCalm, setShownCalm] = useState(calm);

  // Demo only: switching between the usual day and a calm day, in the same render, so that the
  // page never shows the new label with the old cards.
  if (IS_DEMO && shownCalm !== calm) {
    setShownCalm(calm);
    setState(demoState(calm));
  }

  useEffect(() => {
    if (IS_DEMO) return undefined;
    const controller = new AbortController();
    fetch(FEED_URL, { cache: 'no-cache', signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((json) => setState({ status: 'ready', ...normalizeFeed(json) }))
      .catch((error) => {
        if (error.name !== 'AbortError') setState({ status: 'error', generatedAt: null, attacks: [] });
      });
    return () => controller.abort();
  }, []);

  const simulate = useCallback(() => {
    const now = Date.now();
    const alert = normalizeAttack(buildSimulatedAlert(simulated.current, now));
    simulated.current += 1;
    setState((current) => ({ ...current, generatedAt: new Date(now), attacks: [alert, ...current.attacks] }));
    return alert;
  }, []);

  return { ...state, isDemo: IS_DEMO, simulate: IS_DEMO ? simulate : null };
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
 * A value kept in this browser only (localStorage): the profile, doubts reported, checklist
 * ticks. Works without storage too (private mode, blocked site data).
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
