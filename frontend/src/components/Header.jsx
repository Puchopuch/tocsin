import { APP_NAME } from '../config.js';
import { fullDate, updatedAt } from '../lib/format.js';

/**
 * One line: the name, the search, and the time of the last collection, in grey. That time comes
 * from the file written by the collector; without the file, no time is shown.
 */
export default function Header({ status, generatedAt, now, searchRef, query, onQueryChange }) {
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
            Rechercher une attaque
          </label>
          <input
            id="search"
            ref={searchRef}
            type="search"
            placeholder="Rechercher une attaque, une entreprise"
            autoComplete="off"
            spellCheck={false}
            enterKeyHint="search"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            onKeyDown={onKeyDown}
            aria-keyshortcuts="/ Control+K Meta+K"
          />
        </div>

        <p className="site-header__updated">
          {status === 'loading' && 'Chargement'}
          {status === 'error' && 'Données indisponibles'}
          {status === 'ready' && generatedAt && (
            <>
              Mis à jour{' '}
              <time dateTime={generatedAt.toISOString()} title={fullDate(generatedAt)}>
                {updatedAt(generatedAt, now)}
              </time>
            </>
          )}
        </p>
      </div>
    </header>
  );
}
