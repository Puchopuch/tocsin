import { useId } from 'react';
import { Meta, Square } from './Severity.jsx';
import { useLang } from '../lang.jsx';
import { cardDate, fullDate, machineDate, origin, sourcesLine, targets } from '../lib/format.js';

/** Status of the whole card, shown only when it is not confirmed. */
export const cardStatus = (attack, t) => (attack.reliability === 'rumeur' ? t.rumour(attack.reliability_source) : null);

/** Origine, Cibles, Méthode, Impact: grey label, black value; "Non communiqué" when missing. */
export function Facts({ attack }) {
  const { lang, t } = useLang();
  const from = origin(attack.attacker, lang);
  const to = targets(attack.victim, lang);
  const rows = [
    [t.origin, from.value, from.status],
    [t.targets, to.value, to.status],
    [t.method, attack.method || t.notGiven, null],
    [t.impact, attack.loot || t.notGiven, null],
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
  const { t } = useLang();
  return (
    <section className="concern" aria-label={t.concern}>
      <h3 className="concern__title">{t.concern}</h3>
      <p>{attack.am_i_affected || t.notGiven}</p>
      <p>
        <strong>{t.whatToDo}</strong> {attack.action || t.notGiven}
      </p>
    </section>
  );
}

function Foot({ attack, onOpen }) {
  const { lang, t } = useLang();
  return (
    <div className="card__foot">
      <p className="card__sources">{sourcesLine(attack.sources, lang)}</p>
      <button id={`lire-${attack.id}`} type="button" className="link" aria-label={t.readMoreLabel(attack.title)} onClick={() => onOpen(attack.id)}>
        {t.readMore}
      </button>
    </div>
  );
}

/**
 * One attack. "une" is the headline card (title at 40px, "Suis-je concerné ?" alongside);
 * otherwise a card of six rows that lines up with its neighbours.
 */
export default function AttackCard({ attack, now, une = false, onOpen }) {
  const { lang, t } = useLang();
  const titleId = useId();
  const meta = (
    <Meta
      level={attack.severity}
      date={cardDate(attack.first_seen, now, lang)}
      dateTime={machineDate(attack.first_seen)}
      title={fullDate(attack.first_seen, lang)}
      status={cardStatus(attack, t)}
    />
  );

  if (une) {
    return (
      <article className="une" aria-labelledby={titleId}>
        {meta}
        <div className="une__body">
          <div className="grid gap-4">
            <h2 id={titleId} className="une__title" lang={attack.titleLang}>
              {attack.title}
            </h2>
            <p className="card__lede">{attack.lede || t.notGiven}</p>
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
      <h2 id={titleId} className="card__title" lang={attack.titleLang}>
        {attack.title}
      </h2>
      <p className="card__lede">{attack.lede || t.notGiven}</p>
      <Facts attack={attack} />
      <Concern attack={attack} />
      <Foot attack={attack} onOpen={onOpen} />
    </article>
  );
}

/** "En bref": one line per minor attack, without a card. */
export function BriefList({ attacks, now, onOpen }) {
  const { lang, t } = useLang();
  return (
    <ul className="brief__list">
      {attacks.map((attack) => (
        <li key={attack.id} className="brief__row">
          <Square level={attack.severity} />
          <time className="brief__date" dateTime={machineDate(attack.first_seen)} title={fullDate(attack.first_seen, lang)}>
            {cardDate(attack.first_seen, now, lang)}
          </time>
          <span className="brief__name" lang={attack.titleLang}>
            {attack.title}
          </span>
          <button id={`lire-${attack.id}`} type="button" className="link brief__read" aria-label={t.readLabel(attack.title)} onClick={() => onOpen(attack.id)}>
            {t.read}
          </button>
        </li>
      ))}
    </ul>
  );
}
