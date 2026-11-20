import { SEVERITY } from '../lib/severity.js';

/** The 10px square in the level's colour. Decorative: the level is always written next to it. */
export function Square({ level }) {
  return (
    <span
      className={`square square--${level}`}
      style={{ backgroundColor: SEVERITY[level].square }}
      aria-hidden="true"
    />
  );
}

/** First line of a card: square, level in black, short date and, if any, an unconfirmed status. */
export function Meta({ level, date, dateTime, title, status }) {
  return (
    <p className="meta">
      <span className="meta__level">
        <Square level={level} />
        {SEVERITY[level].label}
      </span>
      <time className="meta__date" dateTime={dateTime} title={title}>
        {date}
      </time>
      {status && <span className="meta__status">{status}</span>}
    </p>
  );
}
