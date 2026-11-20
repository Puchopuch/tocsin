import { useId } from 'react';
import { Meta, Square } from './Severity.jsx';
import { cardDate, fullDate, NOT_GIVEN, origin, sourcesLine, targets } from '../lib/format.js';

/** Status of the whole card, shown only when it is not confirmed. */
export const cardStatus = (attack) =>
  attack.reliability === 'rumeur'
    ? `Rumeur${attack.reliability_source ? ` vue sur ${attack.reliability_source}` : ''}, non confirmée`
    : null;

/** Origine, Cibles, Méthode, Impact: grey label, black value; "Non communiqué" when missing. */
export function Facts({ attack }) {
  const from = origin(attack.attacker);
  const to = targets(attack.victim);
  const rows = [
    ['Origine', from.value, from.status],
    ['Cibles', to.value, to.status],
    ['Méthode', attack.method || NOT_GIVEN, null],
    ['Impact', attack.loot || NOT_GIVEN, null],
  ];
  return (
    <dl className="facts">
      {rows.map(([label, value, status]) => (
        <div key={label} className="facts__row">
          <dt>{label}</dt>
          <dd>
            {value}
            {status && <span className="facts__status">{status}</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Concern({ attack }) {
  return (
    <section className="concern" aria-label="Suis-je concerné ?">
      <h3 className="concern__title">Suis-je concerné&nbsp;?</h3>
      <p>{attack.am_i_affected || NOT_GIVEN}</p>
      <p>
        <strong>Que faire&nbsp;:</strong> {attack.action || NOT_GIVEN}
      </p>
    </section>
  );
}

function Foot({ attack, onOpen }) {
  return (
    <div className="card__foot">
      <p className="card__sources">{sourcesLine(attack.sources)}</p>
      <button id={`lire-${attack.id}`} type="button" className="link" aria-label={`Lire la fiche : ${attack.title}`} onClick={() => onOpen(attack.id)}>
        Lire la fiche
      </button>
    </div>
  );
}

/**
 * One attack. "une" is the headline card (title at 40px, "Suis-je concerné ?" alongside);
 * otherwise a card of six rows that lines up with its neighbours.
 */
export default function AttackCard({ attack, now, une = false, onOpen }) {
  const titleId = useId();
  const meta = (
    <Meta
      level={attack.severity}
      date={cardDate(attack.first_seen, now)}
      dateTime={attack.first_seen.toISOString()}
      title={fullDate(attack.first_seen)}
      status={cardStatus(attack)}
    />
  );

  if (une) {
    return (
      <article className="une" aria-labelledby={titleId}>
        {meta}
        <div className="une__body">
          <div className="grid gap-4">
            <h2 id={titleId} className="une__title">
              {attack.title}
            </h2>
            <p className="card__lede">{attack.lede || NOT_GIVEN}</p>
            <Facts attack={attack} />
          </div>
          <Concern attack={attack} />
        </div>
        <Foot attack={attack} onOpen={onOpen} />
      </article>
    );
  }

  return (
    <article className="card" aria-labelledby={titleId}>
      {meta}
      <h2 id={titleId} className="card__title">
        {attack.title}
      </h2>
      <p className="card__lede">{attack.lede || NOT_GIVEN}</p>
      <Facts attack={attack} />
      <Concern attack={attack} />
      <Foot attack={attack} onOpen={onOpen} />
    </article>
  );
}

/** "En bref": one line per minor attack, without a card. */
export function BriefList({ attacks, now, onOpen }) {
  return (
    <ul className="brief__list">
      {attacks.map((attack) => (
        <li key={attack.id} className="brief__row">
          <Square level={attack.severity} />
          <time className="brief__date" dateTime={attack.first_seen.toISOString()} title={fullDate(attack.first_seen)}>
            {cardDate(attack.first_seen, now)}
          </time>
          <span className="brief__name">{attack.title}</span>
          <button id={`lire-${attack.id}`} type="button" className="link brief__read" aria-label={`Lire : ${attack.title}`} onClick={() => onOpen(attack.id)}>
            Lire
          </button>
        </li>
      ))}
    </ul>
  );
}
