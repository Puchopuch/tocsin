// Test feeds for `npm run check` only, in the format of data/cards.json: a usual day of eight
// attacks (one critical, two serious, three significant, one of them a rumour, two minor), a calm
// day, and critical alerts that a test adds on top. Some cards miss a piece of information on
// purpose, as real ones will.
//
// The site never imports this file: the check builds the site and verifies that none of these
// names reached the build. Everything here is fictional and must stay so: every organisation,
// group and app is invented, no real group or country is accused, and real organisations only
// appear as sources marked "(exemple fictif)". Dates are computed from the `now` given.

const HOUR = 3_600_000;

function clock(now) {
  /** ISO date, `hours` before now. */
  const ago = (hours) => new Date(now - hours * HOUR).toISOString();
  /** ISO date `days` ago at "HH:MM", never later than 30 minutes before now. */
  const dayAt = (days, time) => {
    const [hours, minutes] = time.split(':').map(Number);
    const date = new Date(now);
    date.setDate(date.getDate() - days);
    date.setHours(hours, minutes, 0, 0);
    return new Date(Math.min(date.getTime(), now - HOUR / 2)).toISOString();
  };
  return { ago, dayAt };
}

const fictional = (title) => `${title} (exemple fictif)`;
const unknownAttacker = { name: '', country: null, status: 'inconnu', source: null };

function usualDay(now) {
  const { ago, dayAt } = clock(now);
  return [
    {
      id: 'test-telecomx',
      severity: 'critique',
      severity_reason: 'Des données bancaires de 2,4 millions de personnes.',
      title: "Fuite massive de données chez l'opérateur TelecomX",
      lede: "Les noms, adresses e-mail, numéros de téléphone et IBAN de 2,4 millions d'abonnés ont été copiés chez un sous-traitant.",
      first_seen: ago(0.3),
      sector: 'Télécom',
      audience: 'grand_public',
      reliability: 'confirme',
      attacker: unknownAttacker,
      victim: { label: "2,4 millions d'abonnés mobiles", status: 'confirme' },
      method: 'Mot de passe volé chez un sous-traitant',
      loot: 'Noms, e-mails, téléphones et IBAN',
      am_i_affected: 'Oui, si vous étiez client TelecomX avant novembre 2026.',
      action: 'Surveillez vos prélèvements et ignorez les appels qui demandent un code.',
      summary: [
        "Des pirates sont entrés dans l'outil de gestion client d'un sous-traitant de TelecomX avec le mot de passe d'un de ses employés. Ils ont copié les fiches de 2,4 millions d'abonnés mobiles.",
        "Les IBAN, e-mails et numéros de téléphone sont concernés ; pas les mots de passe des comptes, selon l'opérateur. Personne n'a revendiqué l'attaque.",
      ],
      timeline: [
        { date: ago(50), label: 'Connexions suspectes chez le sous-traitant' },
        { date: ago(20), label: "TelecomX coupe l'accès du sous-traitant" },
        { date: ago(0.3), label: 'Annonce publique de TelecomX' },
      ],
      protection_steps: [
        'Vérifiez vos relevés bancaires chaque semaine pendant trois mois.',
        'Contestez tout prélèvement inconnu auprès de votre banque : vous avez 13 mois.',
        "Ne donnez jamais un code reçu par SMS à quelqu'un qui vous appelle.",
      ],
      technical: {
        cves: [],
        software: ['Outil de gestion client du sous-traitant'],
        techniques: [
          { id: 'T1199', name: 'Trusted Relationship' },
          { id: 'T1078', name: 'Valid Accounts' },
        ],
      },
      sources: [
        { name: 'TelecomX', title: fictional('Communiqué aux clients'), url: null, official: true },
        { name: 'CERT-FR', title: fictional('Bulletin sur la fuite'), url: null, official: true },
        { name: 'LeMagIT', title: fictional('Enquête sur la fuite'), url: null, official: false },
      ],
    },
    {
      id: 'test-sms-livraison',
      severity: 'grave',
      severity_reason: 'Des données bancaires volées à grande échelle.',
      title: 'Faux SMS de livraison : des cartes bancaires vidées',
      lede: 'Une vague de SMS réclame quelques euros de frais de livraison et mène à un faux site de paiement.',
      first_seen: ago(5.5),
      sector: 'Arnaque',
      audience: 'grand_public',
      reliability: 'confirme',
      attacker: unknownAttacker,
      victim: { label: 'Particuliers en France', status: 'confirme' },
      method: 'SMS avec un lien vers un faux site',
      loot: 'Numéros de carte et codes de validation',
      am_i_affected: 'Oui, si vous avez payé des « frais de livraison » après un SMS.',
      action: 'Faites opposition sur votre carte, puis appelez votre banque.',
      summary: [
        'Des milliers de SMS annoncent un colis en attente contre quelques euros de frais. Le lien mène à une copie de site de transporteur qui enregistre la carte bancaire.',
        'Les codes de validation saisis servent aussitôt à des achats. La banque Kovalt a repéré la vague et prévient ses clients.',
      ],
      timeline: [
        { date: ago(30), label: 'Premiers SMS signalés' },
        { date: ago(12), label: 'Pic de signalements' },
        { date: ago(5.5), label: 'Alerte publiée par la banque Kovalt' },
      ],
      protection_steps: [
        "N'ouvrez jamais un lien de suivi reçu par SMS : passez par le site du transporteur.",
        'Si vous avez saisi votre carte, faites opposition tout de suite.',
        'Transférez le SMS au 33700, le service de signalement des SMS frauduleux.',
      ],
      technical: { cves: [], software: [], techniques: [{ id: 'T1660', name: 'Phishing' }] },
      sources: [
        { name: 'Banque Kovalt', title: fictional('Alerte aux clients'), url: null, official: true },
        { name: 'Cybermalveillance.gouv.fr', title: fictional('Campagne de faux SMS'), url: null, official: true },
      ],
    },
    {
      id: 'test-amperys',
      severity: 'grave',
      severity_reason: 'Une faille déjà exploitée dans un logiciel répandu.',
      title: 'Une faille exploitée dans un logiciel de réseaux électriques',
      lede: "Ampérys, qui sert à piloter des postes électriques à distance, laissait entrer sans mot de passe par son portail web.",
      first_seen: dayAt(1, '19:40'),
      sector: 'Énergie',
      audience: 'entreprises',
      reliability: 'confirme',
      attacker: { name: 'Groupe Vantor', country: null, status: 'presume', source: 'Ampérys' },
      victim: { label: "Opérateurs d'énergie équipés d'Ampérys", status: 'confirme' },
      method: 'Faille du portail web, sans mot de passe',
      loot: 'Accès aux postes de supervision',
      am_i_affected: 'Oui, si votre entreprise utilise Ampérys avant la version 5.2.1.',
      action: "Installez la version 5.2.1 et fermez l'accès au portail depuis Internet.",
      summary: [
        "Une faille du portail web d'Ampérys permet d'entrer sans mot de passe. Elle a été exploitée avant la sortie du correctif.",
        "L'éditeur attribue ces intrusions au groupe Vantor, sans publier de preuve. Aucune coupure de courant n'est signalée.",
      ],
      timeline: [
        { date: dayAt(3, '07:20'), label: "Intrusions repérées par l'éditeur" },
        { date: dayAt(2, '16:00'), label: 'Correctif publié : version 5.2.1' },
        { date: dayAt(1, '19:40'), label: "Bulletin d'alerte public" },
      ],
      protection_steps: [
        "Installez la version 5.2.1 d'Ampérys sans attendre.",
        "Fermez l'accès au portail depuis Internet, gardez le VPN.",
        'Changez les mots de passe des comptes de supervision.',
      ],
      technical: {
        cves: ['CVE-2026-XXXXX (exemple fictif)'],
        software: ['Ampérys, versions 5.0 à 5.2.0'],
        techniques: [
          { id: 'T1190', name: 'Exploit Public-Facing Application' },
          { id: 'T1133', name: 'External Remote Services' },
        ],
      },
      sources: [
        { name: 'Ampérys', title: fictional('Bulletin de sécurité'), url: null, official: true },
        { name: 'CERT-FR', title: fictional('Alerte sur Ampérys'), url: null, official: true },
      ],
    },
    {
      id: 'test-ondalis',
      severity: 'significative',
      severity_reason: "Rumeur non vérifiée : « Significative » au plus, tant qu'aucune source fiable ne la confirme.",
      title: 'Une fuite de données chez Ondalis ? Une rumeur circule',
      lede: 'Un compte anonyme affirme vendre des données de clients du fournisseur d’accès, sans preuve publiée.',
      first_seen: ago(0.75),
      sector: 'Télécom',
      audience: 'grand_public',
      reliability: 'rumeur',
      reliability_source: 'X',
      attacker: { name: 'Compte anonyme sur X', country: null, status: 'revendique', source: null },
      victim: { label: "Clients d'Ondalis", status: 'revendique' },
      method: null,
      loot: null,
      am_i_affected: "Rien ne le prouve pour l'instant.",
      action: "Ne cliquez sur aucun lien qui accompagne cette rumeur.",
      summary: [
        "Un compte anonyme sur X affirme détenir des données de clients d'Ondalis et propose de les vendre. Aucune preuve n'a été publiée, et Ondalis n'a pas réagi.",
        "Cette fiche existe pour vous éviter les arnaques qui profitent des rumeurs. Elle sera mise à jour dès qu'une source fiable se prononcera.",
      ],
      timeline: [
        { date: ago(2), label: 'Message publié sur X' },
        { date: ago(1.2), label: 'Repris par quelques comptes' },
        { date: ago(0.75), label: 'Fiche ouverte, en attente de confirmation' },
      ],
      protection_steps: [
        'Ne cliquez sur aucun lien partagé autour de cette rumeur.',
        'Ne téléchargez rien de présenté comme des « données volées ».',
      ],
      technical: { cves: [], software: [], techniques: [] },
      sources: [{ name: 'X', title: fictional("Message d'un compte anonyme"), url: null, official: false }],
    },
    {
      id: 'test-faux-rib',
      severity: 'significative',
      severity_reason: "Une centaine d'entreprises touchées, sans fuite de données.",
      title: 'De faux fournisseurs envoient de faux RIB à des PME',
      lede: "Les escrocs piratent la messagerie d'un fournisseur, puis annoncent à ses clients un changement de banque.",
      first_seen: dayAt(1, '16:30'),
      sector: 'Entreprises',
      audience: 'entreprises',
      reliability: 'confirme',
      attacker: unknownAttacker,
      victim: { label: 'Une centaine de PME', status: 'confirme' },
      method: 'Messagerie de fournisseur piratée',
      loot: "Virements détournés, jusqu'à 80 000 €",
      am_i_affected: 'Oui, si un fournisseur vous a annoncé un nouveau RIB par e-mail.',
      action: 'Appelez-le au numéro habituel avant tout virement.',
      summary: [
        'Les escrocs prennent le contrôle de la messagerie de petits fournisseurs, puis écrivent à leurs clients pour annoncer un changement de banque.',
        "Les virements partent vers leurs comptes. Une centaine de PME l'ont signalé cette semaine.",
      ],
      timeline: [
        { date: dayAt(4, '09:00'), label: 'Premières plaintes de PME' },
        { date: dayAt(2, '14:00'), label: 'Mode opératoire identifié' },
        { date: dayAt(1, '16:30'), label: 'Alerte de la préfecture aux entreprises' },
      ],
      protection_steps: [
        'Confirmez par téléphone, au numéro habituel, tout changement de RIB.',
        'Faites valider par deux personnes tout virement inhabituel.',
      ],
      technical: {
        cves: [],
        software: ['Messageries des fournisseurs'],
        techniques: [
          { id: 'T1534', name: 'Internal Spearphishing' },
          { id: 'T1657', name: 'Financial Theft' },
        ],
      },
      sources: [{ name: 'Préfecture de Rives-Ouest', title: fictional('Alerte aux entreprises'), url: null, official: true }],
    },
    {
      id: 'test-vendalo',
      severity: 'significative',
      severity_reason: 'Entre 1 000 et 100 000 personnes, sans donnée sensible.',
      title: '12 000 comptes Vendalo piratés avec des mots de passe réutilisés',
      lede: "Des identifiants volés sur d'autres sites ont ouvert 12 000 comptes clients de la marketplace.",
      first_seen: dayAt(2, '08:15'),
      sector: 'E-commerce',
      audience: 'grand_public',
      reliability: 'confirme',
      attacker: null,
      victim: { label: '12 000 clients de Vendalo', status: 'confirme' },
      method: 'Anciens mots de passe testés en masse',
      loot: 'Adresses, commandes, points de fidélité',
      am_i_affected: 'Oui, si Vendalo vous a demandé de changer de mot de passe.',
      action: "Changez ce mot de passe partout où vous l'utilisiez.",
      summary: [
        "Des pirates ont essayé sur Vendalo des millions d'identifiants volés ailleurs. Ils sont entrés dans 12 000 comptes dont le mot de passe servait aussi sur un autre site.",
        'Ils ont vu les adresses et les commandes, et dépensé des points de fidélité. Les cartes bancaires ne sont pas enregistrées chez Vendalo.',
      ],
      timeline: [
        { date: dayAt(3, '23:10'), label: 'Pic de connexions inhabituelles' },
        { date: dayAt(2, '06:30'), label: 'Comptes touchés bloqués' },
        { date: dayAt(2, '08:15'), label: 'E-mail aux clients concernés' },
      ],
      protection_steps: ['Changez votre mot de passe Vendalo.', "Changez-le aussi partout où vous l'utilisiez."],
      technical: { cves: [], software: ['Espace client Vendalo'], techniques: [{ id: 'T1110.004', name: 'Credential Stuffing' }] },
      sources: [{ name: 'Vendalo', title: fictional('E-mail aux clients'), url: null, official: true }],
    },
    {
      id: 'test-morvalene',
      severity: 'mineure',
      severity_reason: 'Une seule petite structure, touchée quelques heures.',
      title: 'Le site de la mairie de Morvalène défiguré trois heures',
      lede: "La page d'accueil a été remplacée par un message, puis le site a été remis en ligne.",
      first_seen: ago(3.4),
      sector: 'Collectivité',
      audience: 'grand_public',
      reliability: 'confirme',
      attacker: { name: 'Collectif Brisant', country: null, status: 'revendique', source: null },
      victim: { label: 'Site web de la mairie', status: 'confirme' },
      method: 'Extension du site jamais mise à jour',
      loot: "Page d'accueil remplacée, aucune donnée volée",
      am_i_affected: "Non, aucune donnée personnelle n'a été touchée.",
      action: "Passez par l'adresse habituelle du site pour vos démarches.",
      summary: [
        "La page d'accueil du site de Morvalène a été remplacée pendant trois heures par un message du collectif Brisant.",
        "Le site a été remis en ligne dans la journée. Aucune donnée personnelle n'y était stockée.",
      ],
      timeline: [
        { date: ago(6.4), label: "Page d'accueil remplacée" },
        { date: ago(4.8), label: 'Site coupé par la mairie' },
        { date: ago(3.4), label: 'Site remis en ligne' },
      ],
      protection_steps: ["N'ouvrez pas les liens qui figuraient sur la page piratée."],
      technical: { cves: [], software: ['Extension de formulaire du site'], techniques: [{ id: 'T1491.002', name: 'External Defacement' }] },
      sources: [{ name: 'Mairie de Morvalène', title: fictional('Message aux habitants'), url: null, official: true }],
    },
    {
      id: 'test-photoluxe',
      severity: 'mineure',
      severity_reason: 'Moins de 1 000 personnes touchées.',
      title: 'Une fausse appli de retouche photo vole des mots de passe sur Mac',
      lede: "« PhotoLuxe », diffusée par des publicités, copie les mots de passe enregistrés sur l'ordinateur.",
      first_seen: dayAt(2, '11:20'),
      sector: 'Logiciel',
      audience: 'grand_public',
      reliability: 'confirme',
      attacker: unknownAttacker,
      victim: { label: 'Quelques centaines de Mac', status: 'confirme' },
      method: 'Fausse appli gratuite installée par publicité',
      loot: 'Mots de passe enregistrés',
      am_i_affected: "Oui, si vous avez installé « PhotoLuxe » hors de l'App Store.",
      action: "Supprimez l'appli et changez vos mots de passe importants.",
      summary: [
        '« PhotoLuxe », une fausse appli de retouche diffusée par des publicités, copie les mots de passe enregistrés sur le Mac.',
        "Quelques centaines d'installations sont recensées. L'appli n'a jamais été proposée sur l'App Store.",
      ],
      timeline: [
        { date: dayAt(5, '10:00'), label: 'Premières publicités repérées' },
        { date: dayAt(3, '15:30'), label: "Analyse de l'appli publiée" },
        { date: dayAt(2, '11:20'), label: 'Alerte aux utilisateurs de Mac' },
      ],
      protection_steps: ["Supprimez « PhotoLuxe » si vous l'avez installée.", 'Changez les mots de passe de votre messagerie et de votre banque.'],
      technical: { cves: [], software: ['« PhotoLuxe », toutes versions'], techniques: [{ id: 'T1555.001', name: 'Keychain' }] },
      sources: [{ name: 'CERT-FR', title: fictional('Alerte sur une fausse appli'), url: null, official: true }],
    },
  ];
}

// A calm day: minor attacks only.
function calmDay(now) {
  const { ago, dayAt } = clock(now);
  const day = usualDay(now);
  return [
    {
      id: 'test-trameo',
      severity: 'mineure',
      severity_reason: 'Une panne de quelques heures, sans vol de données.',
      title: "L'application des transports Trameo coupée deux heures",
      lede: "Un afflux de fausses connexions a saturé l'application, sans que personne n'y entre.",
      first_seen: ago(2.4),
      sector: 'Transport',
      audience: 'grand_public',
      reliability: 'confirme',
      attacker: unknownAttacker,
      victim: { label: "Application des transports Trameo", status: 'confirme' },
      method: 'Afflux de fausses connexions',
      loot: 'Service coupé, aucune donnée volée',
      am_i_affected: 'Non, sauf pour acheter un titre pendant la panne.',
      action: "Rien à faire : l'application fonctionne de nouveau.",
      summary: [
        "L'application du réseau Trameo a reçu un flot de fausses connexions qui l'a rendue inaccessible pendant deux heures.",
        "Aucune donnée n'a été volée : ce type d'attaque bloque un service sans y entrer.",
      ],
      timeline: [
        { date: ago(4.5), label: 'Application inaccessible' },
        { date: ago(3.2), label: "Trafic filtré par l'hébergeur" },
        { date: ago(2.4), label: 'Retour à la normale' },
      ],
      protection_steps: ["Achetez vos titres dans l'application officielle, comme d'habitude."],
      technical: { cves: [], software: [], techniques: [{ id: 'T1498', name: 'Network Denial of Service' }] },
      sources: [{ name: 'Trameo', title: fictional('Message aux voyageurs'), url: null, official: true }],
    },
    day.find((attack) => attack.id === 'test-morvalene'),
    {
      id: 'test-valtorre',
      severity: 'mineure',
      severity_reason: 'Moins de 1 000 personnes visées, sans intrusion.',
      title: "Un faux concours au nom de l'AS Valtorre circule",
      lede: "Un faux compte du club promet un maillot contre des « frais de port ».",
      first_seen: dayAt(1, '18:10'),
      sector: 'Sport',
      audience: 'grand_public',
      reliability: 'confirme',
      attacker: unknownAttacker,
      victim: { label: 'Supporters du club', status: 'confirme' },
      method: 'Faux compte imitant celui du club',
      loot: 'Quelques coordonnées bancaires',
      am_i_affected: 'Oui, si vous avez joué au concours « maillot offert ».',
      action: 'Faites opposition si vous avez donné votre carte.',
      summary: [
        "Un faux compte imitant celui de l'AS Valtorre promet un maillot offert contre des frais de port. Le club n'organise aucun concours.",
        'Le compte a été suspendu. Quelques centaines de personnes ont participé.',
      ],
      timeline: [
        { date: dayAt(2, '20:00'), label: 'Faux compte créé' },
        { date: dayAt(1, '12:00'), label: 'Premiers signalements de supporters' },
        { date: dayAt(1, '18:10'), label: 'Démenti du club' },
      ],
      protection_steps: ['Faites opposition si vous avez donné votre carte.', 'Ne suivez que le compte officiel du club.'],
      technical: { cves: [], software: [], techniques: [{ id: 'T1585.001', name: 'Social Media Accounts' }] },
      sources: [{ name: 'AS Valtorre', title: fictional('Démenti officiel'), url: null, official: true }],
    },
  ];
}

// Critical alerts that a test adds on top of the usual day, one by one.
const ALERTS = [
  {
    id: 'test-ferlino',
    source: 'Ferlino',
    severity_reason: "Un service vital (transport) paralysé à l'échelle d'une région.",
    title: 'Les trains régionaux Ferlino arrêtés par un rançongiciel',
    lede: 'Les serveurs qui règlent la circulation sont bloqués : les trains sont arrêtés sur 14 lignes.',
    sector: 'Transport',
    victim: { label: '120 000 voyageurs par jour', status: 'confirme' },
    method: 'Rançongiciel sur les serveurs de régulation',
    loot: 'Circulation suspendue sur 14 lignes',
    am_i_affected: "Oui, si vous prenez un train Ferlino aujourd'hui.",
    action: "Vérifiez votre trajet dans l'application avant de partir.",
    summary: [
      'Un rançongiciel a bloqué les serveurs qui règlent la circulation du réseau régional Ferlino. Par sécurité, les trains sont arrêtés sur 14 lignes.',
      "Aucun groupe n'a revendiqué l'attaque. Ferlino annonce une reprise progressive dans la soirée.",
    ],
    steps: [
      [1.5, 'Pannes en cascade sur la régulation'],
      [0.7, 'Circulation suspendue par précaution'],
      [0, 'Alerte publique de Ferlino'],
    ],
    protection_steps: ["Vérifiez votre trajet dans l'application avant de partir.", 'Gardez votre billet : les trajets annulés seront remboursés.'],
    techniques: [{ id: 'T1486', name: 'Data Encrypted for Impact' }],
  },
  {
    id: 'test-valmeuse',
    source: 'Eaux de Valmeuse',
    severity_reason: "Un service vital (l'eau) touché.",
    title: "Des pirates ont pris la main sur le réseau d'eau de Valmeuse",
    lede: "Ils sont entrés par un accès à distance oublié ; les équipes sont passées en commande manuelle.",
    sector: 'Eau',
    victim: { label: '310 000 habitants', status: 'confirme' },
    method: 'Accès à distance oublié, mot de passe par défaut',
    loot: 'Pompes pilotées à distance, coupures',
    am_i_affected: 'Oui, si vous habitez la métropole de Valmeuse.',
    action: 'Suivez uniquement les consignes officielles de la mairie.',
    summary: [
      "Des pirates ont pris le contrôle de pompes du réseau d'eau de Valmeuse grâce à un accès à distance oublié. Les équipes ont repris la main en passant en commande manuelle.",
      "L'eau reste potable selon l'exploitant. Des coupures ponctuelles sont possibles dans la journée.",
    ],
    steps: [
      [3, 'Commandes anormales sur des pompes'],
      [1, 'Passage en commande manuelle'],
      [0, "Alerte de l'exploitant"],
    ],
    protection_steps: ['Suivez uniquement les consignes officielles de la mairie.', "Gardez quelques bouteilles d'eau en réserve aujourd'hui."],
    techniques: [{ id: 'T0822', name: 'External Remote Services' }],
  },
  {
    id: 'test-monetis',
    source: 'Monétis',
    severity_reason: 'Un impact national : le paiement par carte bloqué dans des milliers de magasins.',
    title: 'Le paiement par carte bloqué dans 8 000 magasins',
    lede: 'Les serveurs du réseau Monétis, qui valide les paiements, sont hors ligne depuis ce matin.',
    sector: 'Paiement',
    victim: { label: '8 000 magasins', status: 'confirme' },
    method: 'Serveurs de paiement saturés',
    loot: 'Paiements par carte impossibles',
    am_i_affected: 'Oui, si votre magasin habituel passe par Monétis.',
    action: "Gardez un autre moyen de paiement sur vous aujourd'hui.",
    summary: [
      'Les serveurs du réseau Monétis, qui valide les paiements par carte de 8 000 magasins, sont hors ligne depuis le matin après une attaque.',
      "Aucune donnée bancaire n'aurait été volée. Le retour à la normale est attendu dans la journée.",
    ],
    steps: [
      [2.5, 'Premiers refus de paiement'],
      [1, 'Serveurs mis hors ligne'],
      [0, 'Communiqué de Monétis'],
    ],
    protection_steps: ["Gardez un autre moyen de paiement sur vous aujourd'hui.", 'Méfiez-vous des SMS « de remboursement » liés à la panne.'],
    techniques: [{ id: 'T1498', name: 'Network Denial of Service' }],
  },
];

/** The n-th critical alert, dated now. */
export function buildAlert(n, now) {
  const { ago } = clock(now);
  const { steps, techniques, source, ...alert } = ALERTS[n % ALERTS.length];
  return {
    ...alert,
    id: `${alert.id}-${n + 1}`,
    severity: 'critique',
    first_seen: ago(0),
    audience: 'les_deux',
    reliability: 'confirme',
    attacker: unknownAttacker,
    timeline: steps.map(([hours, label]) => ({ date: ago(hours), label })),
    technical: { cves: [], software: [], techniques },
    sources: [{ name: source, title: fictional('Communiqué officiel'), url: null, official: true }],
  };
}

/** A test feed, as the collector would write it: the usual day, or a calm one. */
export function buildFeed(now, { calm = false } = {}) {
  return {
    generated_at: new Date(now - 12 * 60_000).toISOString(),
    attacks: calm ? calmDay(now) : usualDay(now),
  };
}

/** Names invented for these feeds: none of them may ever appear in the built site. */
export const INVENTED_NAMES = [
  'TelecomX', 'Ondalis', 'Vendalo', 'PhotoLuxe', 'Trameo', 'Valtorre', 'Ferlino', 'Valmeuse',
  'Kovalt', 'Vantor', 'Morval', 'Ampérys', 'Monétis', 'Rives-Ouest', 'test-telecomx',
];
