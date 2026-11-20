import { useId } from 'react';
import Drawer, { DrawerSection } from './Drawer.jsx';
import { Square } from './Severity.jsx';
import { APP_NAME } from '../config.js';
import { CLAIM_RULE, GRID, GRID_INTRO, SEVERITY, STATUS } from '../lib/severity.js';
import { typo } from '../lib/typo.js';

const ORIGINS = [
  ['Autorités', 'CERT-FR, CISA, Cybermalveillance.gouv.fr.'],
  ['Presse spécialisée', 'BleepingComputer, The Record, LeMagIT, ZATAZ.'],
  ['Revendications de pirates', typo('ransomware.live, toujours affichées comme « Revendiqué, non confirmé ».')],
  ['Réseaux sociaux', typo('Mastodon, Bluesky et X, affichés comme « Rumeur, non confirmée » tant que rien ne les confirme.')],
];

const LIMITS = [
  'Les fiches sont rédigées par une IA à partir des sources citées : elles peuvent contenir des erreurs.',
  "L'origine d'une attaque n'est donnée que si une source fiable la donne.",
  'Une information absente est marquée « Non communiqué » plutôt que devinée.',
  'Aucun lien vers les sites des rançonneurs ni vers des données volées.',
  "Les données sont mises à jour toutes les heures : ce n'est pas du direct.",
].map(typo);

/** "Méthode et sources": where the information comes from and how levels are set. */
export default function MethodDrawer({ open, onClose, isDemo }) {
  const titleId = useId();

  return (
    <Drawer open={open} onClose={onClose} labelledBy={titleId} header={<p className="text-black">Méthode et sources</p>}>
      <div className="drawer-body">
        <h2 id={titleId} className="drawer-title">
          Comment {APP_NAME} présente les attaques
        </h2>
        {isDemo && <p className="mt-3">{typo("Données fictives : le vrai flux n'est pas encore branché.")}</p>}

        <DrawerSection title="La gravité">
          <p>{GRID_INTRO}</p>
          <dl className="mt-3 grid gap-3">
            {GRID.map(({ level, criteria }) => (
              <div key={level}>
                <dt className="flex items-center gap-2 font-bold text-black">
                  <Square level={level} />
                  {SEVERITY[level].label}
                </dt>
                <dd>{criteria}</dd>
              </div>
            ))}
          </dl>
        </DrawerSection>

        <DrawerSection title="Les revendications et les rumeurs">
          <p>{CLAIM_RULE}</p>
        </DrawerSection>

        <DrawerSection title="Les statuts">
          <dl className="grid gap-3">
            {Object.entries(STATUS).map(([key, status]) => (
              <div key={key}>
                <dt className="font-bold text-black">{status.label}</dt>
                <dd>{status.meaning}</dd>
              </div>
            ))}
          </dl>
        </DrawerSection>

        <DrawerSection title="D’où viennent les informations">
          <dl className="grid gap-3">
            {ORIGINS.map(([label, text]) => (
              <div key={label}>
                <dt className="font-bold text-black">{label}</dt>
                <dd>{text}</dd>
              </div>
            ))}
          </dl>
        </DrawerSection>

        <DrawerSection title="Les limites">
          {LIMITS.map((limit) => (
            <p key={limit}>{limit}</p>
          ))}
        </DrawerSection>
      </div>
    </Drawer>
  );
}
