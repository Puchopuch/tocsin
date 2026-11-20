import { APP_NAME } from '../config.js';
import { useLang } from '../lang.jsx';
import { fullDate, updatedAt } from '../lib/format.js';

/**
 * One line: the name, the search, the time of the last collection in grey, and FR | EN. That
 * time comes from the file written by the collector; without the file, no time is shown.
 */
export default function Header({ status, generatedAt, now, searchRef, query, onQueryChange }) {
  const { lang, setLang, t } = useLang();

  function onKeyDown(event) {
    if (event.key !== 'Escape') return;
    if (query) onQueryChange('');
    else event.currentTarget.blur();
  }

  return (
    <header className="site-header">
      <div className="page site-header__row">
        <p className="site-header__name">{APP_NAME}</p>

        <div className="site-header__search" role="search">
          <label htmlFor="search" className="sr-only">
            {t.searchLabel}
          </label>
          <input
            id="search"
            ref={searchRef}
            type="search"
            placeholder={t.searchPlaceholder}
            autoComplete="off"
            spellCheck={false}
            enterKeyHint="search"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            onKeyDown={onKeyDown}
            aria-keyshortcuts="/ Control+K Meta+K"
          />
        </div>

        <div className="site-header__side">
          <p className="site-header__updated">
            {status === 'loading' && t.loading}
            {status === 'error' && t.unavailable}
            {status === 'ready' && generatedAt && (
              <>
                {t.updated}{' '}
                <time dateTime={generatedAt.toISOString()} title={fullDate(generatedAt, lang)}>
                  {updatedAt(generatedAt, now, lang)}
                </time>
              </>
            )}
          </p>
          <div className="lang-switch" role="group" aria-label={t.language}>
            <button type="button" lang="fr" aria-pressed={lang === 'fr'} aria-label="Français" onClick={() => setLang('fr')}>
              FR
            </button>
            <span aria-hidden="true">|</span>
            <button type="button" lang="en" aria-pressed={lang === 'en'} aria-label="English" onClick={() => setLang('en')}>
              EN
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
