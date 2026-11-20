import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { MotionConfig } from 'motion/react';
import AttackCard, { BriefList } from './components/AttackCard.jsx';
import AttackDrawer from './components/AttackDrawer.jsx';
import Filters from './components/Filters.jsx';
import Header from './components/Header.jsx';
import MethodDrawer from './components/MethodDrawer.jsx';
import { APP_NAME } from './config.js';
import { localize, useAttacks, useNow, useStored } from './hooks.js';
import { useLang } from './lang.jsx';
import { digest } from './lib/digest.js';
import { matchesQuery, todayLabel, windowStart } from './lib/format.js';
import { LEVELS } from './lib/severity.js';

const ALL = 'toutes';
const rank = (attack) => LEVELS.indexOf(attack.severity);
const dayOf = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
// The newest day first; on the same day, a flaw already exploited before one that is not, at the
// headline as everywhere else; then the latest time.
const byDate = (a, b) =>
  dayOf(b.first_seen) - dayOf(a.first_seen) || Number(b.exploited) - Number(a.exploited) || b.first_seen - a.first_seen;
const bySeverityThenDate = (a, b) => rank(a) - rank(b) || byDate(a, b);

/**
 * How the cards are laid out. On "Toutes": the headline (the most serious, then the most
 * recent) only if there is a critical or serious attack, so that a calm day looks calm; then
 * critical and serious ones in two columns, significant ones in three, minor ones as one line
 * each in "En bref". On the other tabs: that level only, without a headline.
 */
function arrange(cards, severity) {
  if (severity !== ALL) {
    const only = cards.filter((card) => card.severity === severity);
    return {
      une: null,
      serious: severity === 'critique' || severity === 'grave' ? only : [],
      significant: severity === 'significative' ? only : [],
      minor: severity === 'mineure' ? only : [],
    };
  }
  const top = [...cards].sort(bySeverityThenDate)[0];
  const une = top && rank(top) <= 1 ? top : null;
  const rest = cards.filter((card) => card !== une);
  return {
    une,
    serious: rest.filter((card) => rank(card) <= 1).sort(bySeverityThenDate),
    significant: rest.filter((card) => card.severity === 'significative'),
    minor: rest.filter((card) => card.severity === 'mineure'),
  };
}

export default function App() {
  const { lang, t } = useLang();
  const feed = useAttacks();
  const { status, generatedAt } = feed;
  // The cards in the language chosen; both languages stay in the feed.
  const attacks = useMemo(() => localize(feed.attacks, lang), [feed.attacks, lang]);
  const now = useNow();
  const searchRef = useRef(null);

  useEffect(() => {
    document.title = t.title(APP_NAME);
  }, [t]);

  const [severity, setSeverity] = useState(ALL);
  const [query, setQuery] = useState('');
  const [publicOnly, setPublicOnly] = useState(false);
  const [openId, setOpenId] = useState(null);
  const [methodOpen, setMethodOpen] = useState(false);
  const [announcement, setAnnouncement] = useState('');
  const [checklists, setChecklists] = useStored('tocsin.checklists', {});

  // The last seven days, newest first.
  const recent = useMemo(() => attacks.filter((a) => a.first_seen >= windowStart(now)).sort(byDate), [attacks, now]);
  const hasCards = recent.length > 0;

  // Everything but the tab: search and "Grand public uniquement".
  const scoped = useMemo(
    () => recent.filter((a) => (!publicOnly || a.audience !== 'entreprises') && matchesQuery(a, query)),
    [recent, publicOnly, query],
  );

  const counts = useMemo(() => {
    const result = { [ALL]: scoped.length };
    for (const level of LEVELS) result[level] = scoped.filter((a) => a.severity === level).length;
    return result;
  }, [scoped]);

  const summary = useMemo(() => digest(scoped, now, lang), [scoped, now, lang]);
  const layout = useMemo(() => arrange(scoped, severity), [scoped, severity]);
  const shown = (layout.une ? 1 : 0) + layout.serious.length + layout.significant.length + layout.minor.length;

  const openAttack = useMemo(() => attacks.find((a) => a.id === openId) ?? null, [attacks, openId]);
  const panelOpen = openAttack !== null || methodOpen;

  // "/" and Ctrl+K (⌘K) jump to the search field.
  useEffect(() => {
    function onKeyDown(event) {
      if (panelOpen) return;
      const target = event.target;
      // Only fields where "/" can be typed; a checkbox or a button does not count.
      const typing =
        target instanceof HTMLElement &&
        (target.isContentEditable ||
          ['TEXTAREA', 'SELECT'].includes(target.tagName) ||
          (target.tagName === 'INPUT' && !['checkbox', 'radio', 'button', 'submit'].includes(target.type)));
      if (event.key.toLowerCase() === 'k' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
      } else if (event.key === '/' && !typing && !event.metaKey && !event.ctrlKey && !event.altKey) {
        event.preventDefault();
        searchRef.current?.focus();
      }
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [panelOpen]);

  // Screen readers hear how many attacks are shown after each change of filter.
  const filters = `${severity}|${publicOnly}|${query}`;
  const lastFilters = useRef(filters);
  useEffect(() => {
    if (lastFilters.current === filters) return undefined;
    lastFilters.current = filters;
    const timer = setTimeout(() => setAnnouncement(t.shown(shown)), 500);
    return () => clearTimeout(timer);
  }, [filters, shown, t]);

  const resetFilters = useCallback(() => {
    setSeverity(ALL);
    setQuery('');
    setPublicOnly(false);
  }, []);

  const toggleStep = useCallback(
    (id, index) =>
      setChecklists((all) => {
        const steps = all[id] ?? [];
        return { ...all, [id]: steps.includes(index) ? steps.filter((x) => x !== index) : [...steps, index] };
      }),
    [setChecklists],
  );

  const openSheet = useCallback((id) => setOpenId(id), []);
  const closeSheet = useCallback(() => setOpenId(null), []);
  const openMethod = useCallback(() => setMethodOpen(true), []);
  const closeMethod = useCallback(() => setMethodOpen(false), []);

  return (
    <MotionConfig reducedMotion="user">
      <div className="flex min-h-dvh flex-col" inert={panelOpen}>
        <a href="#attaques" className="skip-link">
          {t.skip}
        </a>

        <Header status={status} generatedAt={generatedAt} now={now} searchRef={searchRef} query={query} onQueryChange={setQuery} />

        <main className="flex-1">
          <h1 className="sr-only">{t.title(APP_NAME)}</h1>
          <div className="page digest">
            <p className="digest__date">{todayLabel(now, lang)}</p>
            {hasCards && <p className="digest__text">{summary}</p>}
          </div>

          {hasCards && (
            <Filters severity={severity} onSeverityChange={setSeverity} counts={counts} publicOnly={publicOnly} onPublicOnlyChange={setPublicOnly} />
          )}

          <section id="attaques" tabIndex={-1} aria-label={t.attacks} className="page results outline-none">
            {status === 'loading' && <p className="state">{t.loadingAttacks}</p>}
            {status === 'error' && <p className="state">{t.loadError}</p>}
            {(status === 'empty' || status === 'ready') && !hasCards && <p className="state">{t.noAttack}</p>}
            {hasCards && shown === 0 && (
              <div className="state">
                <p>{t.noMatch}</p>
                <button type="button" className="link mt-2" onClick={resetFilters}>
                  {t.showAll}
                </button>
              </div>
            )}

            {layout.une && <AttackCard attack={layout.une} now={now} une onOpen={openSheet} />}

            {layout.serious.length > 0 && (
              <div className="grid-cards grid-cards--2">
                {layout.serious.map((attack) => (
                  <AttackCard key={attack.id} attack={attack} now={now} onOpen={openSheet} />
                ))}
              </div>
            )}

            {layout.significant.length > 0 && (
              <div className="grid-cards grid-cards--3">
                {layout.significant.map((attack) => (
                  <AttackCard key={attack.id} attack={attack} now={now} onOpen={openSheet} />
                ))}
              </div>
            )}

            {layout.minor.length > 0 &&
              (severity === ALL ? (
                <section aria-labelledby="en-bref">
                  <h2 id="en-bref" className="brief__title">
                    {t.inBrief}
                  </h2>
                  <BriefList attacks={layout.minor} now={now} onOpen={openSheet} />
                </section>
              ) : (
                <BriefList attacks={layout.minor} now={now} onOpen={openSheet} />
              ))}
          </section>
        </main>

        <footer className="page site-footer">
          <p>{t.footer}</p>
          <button type="button" className="link" onClick={openMethod}>
            {t.methodLink}
          </button>
        </footer>

        <p className="sr-only" aria-live="polite">
          {announcement}
        </p>
      </div>

      <AttackDrawer
        attack={openAttack}
        now={now}
        done={openAttack ? checklists[openAttack.id] : undefined}
        onToggleStep={toggleStep}
        onClose={closeSheet}
      />
      <MethodDrawer open={methodOpen} onClose={closeMethod} />
    </MotionConfig>
  );
}
