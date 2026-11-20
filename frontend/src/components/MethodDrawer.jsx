import { useId } from 'react';
import Drawer, { DrawerSection } from './Drawer.jsx';
import { Square } from './Severity.jsx';
import { APP_NAME } from '../config.js';
import { CLAIM_RULE, GRID, GRID_INTRO, SEVERITY, STATUS } from '../lib/severity.js';
import { typo } from '../lib/typo.js';

// The sources the collector reads today, and nothing else.
const ORIGINS = [
  ['Autorités', 'CISA, l’agence américaine de cybersécurité (failles déjà exploitées), et CERT-FR (alertes).'],
  ['Revendications de pirates', typo('ransomware.live, toujours affichées comme « Revendiqué, non confirmé ».')],
];

const LIMITS = [
  'Les fiches sont construites automatiquement à partir des sources citées : si une source se trompe, la fiche aussi.',
  "L'origine d'une attaque n'est donnée que si une source fiable la donne.",
  'Une information absente est marquée « Non communiqué » plutôt que devinée.',
  "Aucune donnée personnelle : une revendication dont la victime pourrait être une personne n'est pas publiée.",
  'Aucun lien vers les sites des rançonneurs ni vers des données volées.',
  "Les données sont mises à jour à chaque collecte, dont l'heure est affichée en haut de la page : ce n'est pas du direct.",
].map(typo);

/** "Méthode et sources": where the information comes from and how levels are set. */
export default function MethodDrawer({ open, onClose }) {
  const titleId = useId();

  return (
    <Drawer open={open} onClose={onClose} labelledBy={titleId} header={<p className="text-black">Méthode et sources</p>}>
      <div className="drawer-body">
        <h2 id={titleId} className="drawer-title">
          Comment {APP_NAME} présente les attaques
        </h2>

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
