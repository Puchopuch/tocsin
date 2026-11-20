import { useId, useRef } from 'react';
import Drawer, { DrawerSection } from './Drawer.jsx';
import { cardStatus, Facts } from './AttackCard.jsx';
import { Meta } from './Severity.jsx';
import { useLang } from '../lang.jsx';
import { attackUrl, cardDate, fullDate, machineDate, orderSources, timelineDate } from '../lib/format.js';

/** "Lire la fiche": everything known about one attack, with its sources. */
export default function AttackDrawer({ attack, now, done, onToggleStep, onClose }) {
  const { lang, t } = useLang();
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
            date={cardDate(current.first_seen, now, lang)}
            dateTime={machineDate(current.first_seen)}
            title={fullDate(current.first_seen, lang)}
            status={cardStatus(current, t)}
          />
        )
      }
    >
      {current && <Sheet attack={current} now={now} titleId={titleId} done={done ?? []} onToggleStep={onToggleStep} />}
    </Drawer>
  );
}

function Sheet({ attack, now, titleId, done, onToggleStep }) {
  const { lang, t } = useLang();
  const { technical } = attack;
  const timeline = [...attack.timeline].sort((a, b) => a.date - b.date);
  const steps = attack.protection_steps;
  const doneCount = steps.filter((_, index) => done.includes(index)).length;

  return (
    <div className="drawer-body">
      <h2 id={titleId} className="drawer-title" lang={attack.titleLang}>
        {attack.title}
      </h2>
      <p className="mt-3">{attack.lede || t.notGiven}</p>
      <p className="mt-2 text-[14px] text-muted">
        {t.detected} <time dateTime={machineDate(attack.first_seen)}>{fullDate(attack.first_seen, lang)}</time>
      </p>

      <div className="mt-6">
        <Facts attack={attack} />
      </div>

      <section className="concern mt-6" aria-labelledby={`${titleId}-concern`}>
        <h3 id={`${titleId}-concern`} className="concern__title">
          {t.concern}
        </h3>
        <p>{attack.am_i_affected || t.notGiven}</p>
        <p>
          <strong>{t.whatToDo}</strong> {attack.action || t.notGiven}
        </p>
        {steps.length > 0 && (
          <>
            <p className="mt-4 text-[14px] text-muted" aria-live="polite">
              {t.stepsDone(doneCount, steps.length)}
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
        <DrawerSection title={t.happened}>
          {attack.summary.map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
          {attack.severity_reason && (
            <p className="text-[14px] text-muted">
              {t.why} {attack.severity_reason}
            </p>
          )}
        </DrawerSection>
      )}

      {timeline.length > 0 && (
        <DrawerSection title={t.timeline}>
          <ol className="timeline">
            {timeline.map((event, index) => (
              <li key={index}>
                <time dateTime={machineDate(event.date)} title={fullDate(event.date, lang)}>
                  {timelineDate(event.date, now, lang)}
                </time>
                <span>{event.label}</span>
              </li>
            ))}
          </ol>
        </DrawerSection>
      )}

      <details className="drawer-section tech">
        <summary>{t.technical}</summary>
        <dl>
          <div>
            <dt>{t.cves}</dt>
            <dd>{technical.cves.length > 0 ? technical.cves.join(', ') : t.noCve}</dd>
          </div>
          <div>
            <dt>{t.software}</dt>
            <dd>{technical.software.length > 0 ? technical.software.join(', ') : t.notGiven}</dd>
          </div>
          <div>
            <dt>{t.techniques}</dt>
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
                t.notGiven
              )}
            </dd>
          </div>
        </dl>
      </details>

      <DrawerSection title={t.sources}>
        {attack.sources.length > 0 ? (
          <ul className="sources">
            {orderSources(attack.sources).map((source, index) => (
              <li key={index}>
                <p className="text-black">
                  {source.name}
                  {source.official && <span className="text-muted">{t.officialSource}</span>}
                </p>
                {source.title && <p className="sources__title">{source.title}</p>}
                {source.url ? (
                  <a className="link text-[14px]" href={source.url} target="_blank" rel="noopener noreferrer">
                    {t.openSource}
                    <span className="sr-only">
                      {' '}
                      {source.name} {t.newTab}
                    </span>
                  </a>
                ) : (
                  <p className="sources__title">{t.noLink}</p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p>{t.notGiven}</p>
        )}
      </DrawerSection>
    </div>
  );
}

function TechniqueLink({ technique }) {
  const { t } = useLang();
  const url = attackUrl(technique.id);
  const label = `${technique.id}, ${technique.name}`;
  if (!url) return label;
  return (
    <a className="link" href={url} target="_blank" rel="noopener noreferrer">
      {label}
      <span className="sr-only"> {t.newTab}</span>
    </a>
  );
}
