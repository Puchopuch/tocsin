import { useId, useRef } from 'react';
import Drawer, { DrawerSection } from './Drawer.jsx';
import { cardStatus, Facts } from './AttackCard.jsx';
import { Meta } from './Severity.jsx';
import { attackUrl, cardDate, fullDate, NOT_GIVEN, orderSources, timelineDate } from '../lib/format.js';

/** "Lire la fiche": everything known about one attack, with its sources. */
export default function AttackDrawer({ attack, now, done, onToggleStep, onClose }) {
  const titleId = useId();
  // Keep showing the last attack while the panel slides out.
  const shown = useRef(attack);
  if (attack) shown.current = attack;
  const current = attack ?? shown.current;

  return (
    <Drawer
      open={attack !== null}
      onClose={onClose}
      labelledBy={titleId}
      header={
        current && (
          <Meta
            level={current.severity}
            date={cardDate(current.first_seen, now)}
            dateTime={current.first_seen.toISOString()}
            title={fullDate(current.first_seen)}
            status={cardStatus(current)}
          />
        )
      }
    >
      {current && <Sheet attack={current} now={now} titleId={titleId} done={done ?? []} onToggleStep={onToggleStep} />}
    </Drawer>
  );
}

function Sheet({ attack, now, titleId, done, onToggleStep }) {
  const { technical } = attack;
  const timeline = [...attack.timeline].sort((a, b) => a.date - b.date);
  const steps = attack.protection_steps;
  const doneCount = steps.filter((_, index) => done.includes(index)).length;

  return (
    <div className="drawer-body">
      <h2 id={titleId} className="drawer-title">
        {attack.title}
      </h2>
      <p className="mt-3">{attack.lede || NOT_GIVEN}</p>
      <p className="mt-2 text-[14px] text-muted">
        Détectée le <time dateTime={attack.first_seen.toISOString()}>{fullDate(attack.first_seen)}</time>
      </p>

      <div className="mt-6">
        <Facts attack={attack} />
      </div>

      <section className="concern mt-6" aria-labelledby={`${titleId}-concern`}>
        <h3 id={`${titleId}-concern`} className="concern__title">
          Suis-je concerné&nbsp;?
        </h3>
        <p>{attack.am_i_affected || NOT_GIVEN}</p>
        <p>
          <strong>Que faire&nbsp;:</strong> {attack.action || NOT_GIVEN}
        </p>
        {steps.length > 0 && (
          <>
            <p className="mt-4 text-[14px] text-muted" aria-live="polite">
              Étapes faites&nbsp;: {doneCount} sur {steps.length}
            </p>
            <ul className="steps">
              {steps.map((step, index) => (
                <li key={index}>
                  <label>
                    <input type="checkbox" checked={done.includes(index)} onChange={() => onToggleStep(attack.id, index)} />
                    <span>{step}</span>
                  </label>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      {attack.summary.length > 0 && (
        <DrawerSection title="Ce qui s’est passé">
          {attack.summary.map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
          {attack.severity_reason && (
            <p className="text-[14px] text-muted">Pourquoi ce niveau&nbsp;: {attack.severity_reason}</p>
          )}
        </DrawerSection>
      )}

      {timeline.length > 0 && (
        <DrawerSection title="Chronologie">
          <ol className="timeline">
            {timeline.map((event, index) => (
              <li key={index}>
                <time dateTime={event.date.toISOString()} title={fullDate(event.date)}>
                  {timelineDate(event.date, now)}
                </time>
                <span>{event.label}</span>
              </li>
            ))}
          </ol>
        </DrawerSection>
      )}

      <details className="drawer-section tech">
        <summary>Détails techniques</summary>
        <dl>
          <div>
            <dt>Failles (CVE)</dt>
            <dd>{technical.cves.length > 0 ? technical.cves.join(', ') : 'Aucune CVE publiée'}</dd>
          </div>
          <div>
            <dt>Logiciels concernés</dt>
            <dd>{technical.software.length > 0 ? technical.software.join(', ') : NOT_GIVEN}</dd>
          </div>
          <div>
            <dt>Techniques (MITRE ATT&amp;CK)</dt>
            <dd>
              {technical.techniques.length > 0 ? (
                <ul>
                  {technical.techniques.map((technique) => (
                    <li key={technique.id}>
                      <TechniqueLink technique={technique} />
                    </li>
                  ))}
                </ul>
              ) : (
                NOT_GIVEN
              )}
            </dd>
          </div>
        </dl>
      </details>

      <DrawerSection title="Sources">
        {attack.sources.length > 0 ? (
          <ul className="sources">
            {orderSources(attack.sources).map((source, index) => (
              <li key={index}>
                <p className="text-black">
                  {source.name}
                  {source.official && <span className="text-muted">, source officielle</span>}
                </p>
                {source.title && <p className="sources__title">{source.title}</p>}
                {source.url ? (
                  <a className="link text-[14px]" href={source.url} target="_blank" rel="noopener noreferrer">
                    Ouvrir la source<span className="sr-only"> {source.name} (nouvel onglet)</span>
                  </a>
                ) : (
                  <p className="sources__title">Pas de lien</p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p>{NOT_GIVEN}</p>
        )}
      </DrawerSection>
    </div>
  );
}

function TechniqueLink({ technique }) {
  const url = attackUrl(technique.id);
  const label = `${technique.id}, ${technique.name}`;
  if (!url) return label;
  return (
    <a className="link" href={url} target="_blank" rel="noopener noreferrer">
      {label}
      <span className="sr-only"> (nouvel onglet)</span>
    </a>
  );
}
