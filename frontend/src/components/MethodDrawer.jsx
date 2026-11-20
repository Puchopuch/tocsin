import { useId } from 'react';
import Drawer, { DrawerSection } from './Drawer.jsx';
import { Square } from './Severity.jsx';
import { APP_NAME } from '../config.js';
import { useLang } from '../lang.jsx';
import { CLAIM_RULE, GRID, GRID_INTRO, LEVEL_NAMES, STATUS } from '../lib/severity.js';

/** "Méthode et sources": where the information comes from and how levels are set. */
export default function MethodDrawer({ open, onClose }) {
  const { lang, t } = useLang();
  const titleId = useId();

  return (
    <Drawer open={open} onClose={onClose} labelledBy={titleId} header={<p className="text-black">{t.methodLink}</p>}>
      <div className="drawer-body">
        <h2 id={titleId} className="drawer-title">
          {t.methodTitle(APP_NAME)}
        </h2>

        <DrawerSection title={t.severityTitle}>
          <p>{GRID_INTRO[lang]}</p>
          <dl className="mt-3 grid gap-3">
            {GRID[lang].map(({ level, criteria }) => (
              <div key={level}>
                <dt className="flex items-center gap-2 font-bold text-black">
                  <Square level={level} />
                  {LEVEL_NAMES[lang][level].label}
                </dt>
                <dd>{criteria}</dd>
              </div>
            ))}
          </dl>
        </DrawerSection>

        <DrawerSection title={t.claimsTitle}>
          <p>{CLAIM_RULE[lang]}</p>
        </DrawerSection>

        <DrawerSection title={t.statusesTitle}>
          <dl className="grid gap-3">
            {Object.entries(STATUS).map(([key, status]) => (
              <div key={key}>
                <dt className="font-bold text-black">{status[lang].label}</dt>
                <dd>{status[lang].meaning}</dd>
              </div>
            ))}
          </dl>
        </DrawerSection>

        <DrawerSection title={t.originsTitle}>
          <dl className="grid gap-3">
            {t.origins.map(([label, text]) => (
              <div key={label}>
                <dt className="font-bold text-black">{label}</dt>
                <dd>{text}</dd>
              </div>
            ))}
          </dl>
        </DrawerSection>

        <DrawerSection title={t.limitsTitle}>
          {t.limits.map((limit) => (
            <p key={limit}>{limit}</p>
          ))}
        </DrawerSection>
      </div>
    </Drawer>
  );
}
