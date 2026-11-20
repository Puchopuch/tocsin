import { LEVELS, SEVERITY } from '../lib/severity.js';

/**
 * Tabs with their counts, underlined when active, and "Grand public uniquement" on the right.
 * Counts follow the search and the checkbox, not the tab.
 */
export default function Filters({ severity, onSeverityChange, counts, publicOnly, onPublicOnlyChange }) {
  const tabs = [{ key: 'toutes', label: 'Toutes' }, ...LEVELS.map((level) => ({ key: level, label: SEVERITY[level].label }))];

  return (
    <div className="page filters">
      <div role="group" aria-label="Filtrer par gravité" className="tabs">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className="tab"
            aria-pressed={severity === tab.key}
            onClick={() => onSeverityChange(tab.key)}
          >
            {tab.label} <span className="tab__count">{counts[tab.key]}</span>
          </button>
        ))}
      </div>

      <label className="public-only">
        <input type="checkbox" checked={publicOnly} onChange={(event) => onPublicOnlyChange(event.target.checked)} />
        Grand public uniquement
      </label>
    </div>
  );
}
