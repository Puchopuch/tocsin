// Test feeds for `npm run check` only, in the format of data/cards.json, every text in French and
// in English: a usual day of eight attacks (one critical, two severe, three significant, one of
// them a rumour, two minor), a calm day, and critical alerts that a test adds on top. Some cards
// miss a piece of information on purpose, as real ones will.
//
// The site never imports this file: the check builds the site and verifies that none of these
// names reached the build. Everything here is fictional and must stay so: every organisation,
// group and app is invented, no real group or country is accused, and real organisations only
// appear as sources marked "(exemple fictif)" / "(fictional example)". Dates are computed from
// the `now` given.

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

/** A text in both languages. */
const t = (fr, en) => ({ fr, en });
const fictional = (fr, en) => t(`${fr} (exemple fictif)`, `${en} (fictional example)`);
const unknownAttacker = { name: null, country: null, status: 'inconnu', source: null };

function usualDay(now) {
  const { ago, dayAt } = clock(now);
  return [
    {
      id: 'test-telecomx',
      severity: 'critique',
      severity_reason: t('Des données bancaires de 2,4 millions de personnes.', 'Banking data of 2.4 million people.'),
      title: t("Fuite massive de données chez l'opérateur TelecomX", 'Massive data leak at the operator TelecomX'),
      lede: t(
        "Les noms, adresses e-mail, numéros de téléphone et IBAN de 2,4 millions d'abonnés ont été copiés chez un sous-traitant.",
        'The names, e-mail addresses, phone numbers and IBANs of 2.4 million subscribers were copied at a subcontractor.',
      ),
      first_seen: ago(0.3),
      sector: t('Télécom', 'Telecoms'),
      audience: 'grand_public',
      reliability: 'confirme',
      attacker: unknownAttacker,
      victim: { label: t("2,4 millions d'abonnés mobiles", '2.4 million mobile subscribers'), status: 'confirme' },
      method: t('Mot de passe volé chez un sous-traitant', 'Password stolen at a subcontractor'),
      loot: t('Noms, e-mails, téléphones et IBAN', 'Names, e-mails, phones and IBANs'),
      am_i_affected: t('Oui, si vous étiez client TelecomX avant novembre 2026.', 'Yes, if you were a TelecomX customer before November 2026.'),
      action: t('Surveillez vos prélèvements et ignorez les appels qui demandent un code.', 'Watch your direct debits and ignore calls that ask for a code.'),
      summary: [
        t(
          "Des pirates sont entrés dans l'outil de gestion client d'un sous-traitant de TelecomX avec le mot de passe d'un de ses employés. Ils ont copié les fiches de 2,4 millions d'abonnés mobiles.",
          'Attackers got into the customer management tool of a TelecomX subcontractor with the password of one of its employees. They copied the records of 2.4 million mobile subscribers.',
        ),
        t(
          "Les IBAN, e-mails et numéros de téléphone sont concernés ; pas les mots de passe des comptes, selon l'opérateur. Personne n'a revendiqué l'attaque.",
          'IBANs, e-mails and phone numbers are concerned; not the account passwords, according to the operator. Nobody has claimed the attack.',
        ),
      ],
      timeline: [
        { date: ago(50), label: t('Connexions suspectes chez le sous-traitant', 'Suspicious logins at the subcontractor') },
        { date: ago(20), label: t("TelecomX coupe l'accès du sous-traitant", 'TelecomX cuts off the subcontractor’s access') },
        { date: ago(0.3), label: t('Annonce publique de TelecomX', 'Public announcement by TelecomX') },
      ],
      protection_steps: [
        t('Vérifiez vos relevés bancaires chaque semaine pendant trois mois.', 'Check your bank statements every week for three months.'),
        t('Contestez tout prélèvement inconnu auprès de votre banque : vous avez 13 mois.', 'Dispute any unknown direct debit with your bank: you have 13 months.'),
        t("Ne donnez jamais un code reçu par SMS à quelqu'un qui vous appelle.", 'Never give a code received by text message to someone who calls you.'),
      ],
      technical: {
        cves: [],
        software: [t('Outil de gestion client du sous-traitant', 'Customer management tool of the subcontractor')],
        techniques: [
          { id: 'T1199', name: 'Trusted Relationship' },
          { id: 'T1078', name: 'Valid Accounts' },
        ],
      },
      sources: [
        { name: 'TelecomX', title: fictional('Communiqué aux clients', 'Notice to customers'), url: null, official: true },
        { name: 'CERT-FR', title: fictional('Bulletin sur la fuite', 'Bulletin on the leak'), url: null, official: true },
        { name: 'LeMagIT', title: fictional('Enquête sur la fuite', 'Investigation into the leak'), url: null, official: false },
      ],
    },
    {
      id: 'test-sms-livraison',
      severity: 'grave',
      severity_reason: t('Des données bancaires volées à grande échelle.', 'Banking data stolen on a large scale.'),
      title: t('Faux SMS de livraison : des cartes bancaires vidées', 'Fake delivery texts: bank cards emptied'),
      lede: t(
        'Une vague de SMS réclame quelques euros de frais de livraison et mène à un faux site de paiement.',
        'A wave of text messages asks for a few euros of delivery fees and leads to a fake payment site.',
      ),
      first_seen: ago(5.5),
      sector: t('Arnaque', 'Scam'),
      audience: 'grand_public',
      reliability: 'confirme',
      attacker: unknownAttacker,
      victim: { label: t('Particuliers en France', 'Individuals in France'), status: 'confirme' },
      method: t('SMS avec un lien vers un faux site', 'Text message linking to a fake site'),
      loot: t('Numéros de carte et codes de validation', 'Card numbers and validation codes'),
      am_i_affected: t('Oui, si vous avez payé des « frais de livraison » après un SMS.', 'Yes, if you paid “delivery fees” after a text message.'),
      action: t('Faites opposition sur votre carte, puis appelez votre banque.', 'Block your card, then call your bank.'),
      summary: [
        t(
          'Des milliers de SMS annoncent un colis en attente contre quelques euros de frais. Le lien mène à une copie de site de transporteur qui enregistre la carte bancaire.',
          'Thousands of text messages announce a parcel waiting against a few euros of fees. The link leads to a copy of a carrier’s site that records the bank card.',
        ),
        t(
          'Les codes de validation saisis servent aussitôt à des achats. La banque Kovalt a repéré la vague et prévient ses clients.',
          'The validation codes typed in are used at once for purchases. Kovalt bank spotted the wave and is warning its customers.',
        ),
      ],
      timeline: [
        { date: ago(30), label: t('Premiers SMS signalés', 'First text messages reported') },
        { date: ago(12), label: t('Pic de signalements', 'Peak of reports') },
        { date: ago(5.5), label: t('Alerte publiée par la banque Kovalt', 'Alert published by Kovalt bank') },
      ],
      protection_steps: [
        t("N'ouvrez jamais un lien de suivi reçu par SMS : passez par le site du transporteur.", 'Never open a tracking link received by text message: go through the carrier’s site.'),
        t('Si vous avez saisi votre carte, faites opposition tout de suite.', 'If you typed in your card, block it right away.'),
        t('Signalez le SMS au service de signalement des SMS frauduleux.', 'Report the text message to the service for fraudulent texts.'),
      ],
      technical: { cves: [], software: [], techniques: [{ id: 'T1660', name: 'Phishing' }] },
      sources: [
        { name: 'Banque Kovalt', title: fictional('Alerte aux clients', 'Alert to customers'), url: null, official: true },
        { name: 'Cybermalveillance.gouv.fr', title: fictional('Campagne de faux SMS', 'Fake text message campaign'), url: null, official: true },
      ],
    },
    {
      id: 'test-amperys',
      severity: 'grave',
      severity_reason: t('Une faille déjà exploitée dans un logiciel répandu.', 'A flaw already exploited in widespread software.'),
      title: t('Une faille exploitée dans un logiciel de réseaux électriques', 'A flaw exploited in power grid software'),
      lede: t(
        'Ampérys, qui sert à piloter des postes électriques à distance, laissait entrer sans mot de passe par son portail web.',
        'Ampérys, used to control electrical substations remotely, let anyone in without a password through its web portal.',
      ),
      first_seen: dayAt(1, '19:40'),
      sector: t('Énergie', 'Energy'),
      audience: 'entreprises',
      reliability: 'confirme',
      attacker: { name: t('Groupe Vantor', 'Vantor group'), country: null, status: 'presume', source: 'Ampérys' },
      victim: { label: t("Opérateurs d'énergie équipés d'Ampérys", 'Energy operators using Ampérys'), status: 'confirme' },
      method: t('Faille du portail web, sans mot de passe', 'Web portal flaw, no password needed'),
      loot: t('Accès aux postes de supervision', 'Access to supervision stations'),
      am_i_affected: t('Oui, si votre entreprise utilise Ampérys avant la version 5.2.1.', 'Yes, if your company uses Ampérys before version 5.2.1.'),
      action: t("Installez la version 5.2.1 et fermez l'accès au portail depuis Internet.", 'Install version 5.2.1 and close access to the portal from the Internet.'),
      summary: [
        t(
          "Une faille du portail web d'Ampérys permet d'entrer sans mot de passe. Elle a été exploitée avant la sortie du correctif.",
          'A flaw in the Ampérys web portal lets anyone in without a password. It was exploited before the fix came out.',
        ),
        t(
          "L'éditeur attribue ces intrusions au groupe Vantor, sans publier de preuve. Aucune coupure de courant n'est signalée.",
          'The vendor attributes these intrusions to the Vantor group, without publishing proof. No power cut is reported.',
        ),
      ],
      timeline: [
        { date: dayAt(3, '07:20'), label: t("Intrusions repérées par l'éditeur", 'Intrusions spotted by the vendor') },
        { date: dayAt(2, '16:00'), label: t('Correctif publié : version 5.2.1', 'Fix published: version 5.2.1') },
        { date: dayAt(1, '19:40'), label: t("Bulletin d'alerte public", 'Public alert bulletin') },
      ],
      protection_steps: [
        t("Installez la version 5.2.1 d'Ampérys sans attendre.", 'Install version 5.2.1 of Ampérys without delay.'),
        t("Fermez l'accès au portail depuis Internet, gardez le VPN.", 'Close access to the portal from the Internet, keep the VPN.'),
        t('Changez les mots de passe des comptes de supervision.', 'Change the passwords of the supervision accounts.'),
      ],
      technical: {
        cves: ['CVE-2026-XXXXX (exemple fictif)'],
        software: [t('Ampérys, versions 5.0 à 5.2.0', 'Ampérys, versions 5.0 to 5.2.0')],
        techniques: [
          { id: 'T1190', name: 'Exploit Public-Facing Application' },
          { id: 'T1133', name: 'External Remote Services' },
        ],
      },
      sources: [
        { name: 'Ampérys', title: fictional('Bulletin de sécurité', 'Security bulletin'), url: null, official: true },
        { name: 'CERT-FR', title: fictional('Alerte sur Ampérys', 'Alert on Ampérys'), url: null, official: true },
      ],
    },
    {
      id: 'test-ondalis',
      severity: 'significative',
      severity_reason: t(
        "Rumeur non vérifiée : « Significative » au plus, tant qu'aucune source fiable ne la confirme.",
        'Unverified rumour: “Significant” at most, until a reliable source confirms it.',
      ),
      title: t('Une fuite de données chez Ondalis ? Une rumeur circule', 'A data leak at Ondalis? A rumour is going round'),
      lede: t(
        'Un compte anonyme affirme vendre des données de clients du fournisseur d’accès, sans preuve publiée.',
        'An anonymous account claims to sell customer data of the internet provider, without published proof.',
      ),
      first_seen: ago(0.75),
      sector: t('Télécom', 'Telecoms'),
      audience: 'grand_public',
      reliability: 'rumeur',
      reliability_source: 'X',
      attacker: { name: t('Compte anonyme sur X', 'Anonymous account on X'), country: null, status: 'revendique', source: null },
      victim: { label: t("Clients d'Ondalis", 'Ondalis customers'), status: 'revendique' },
      method: null,
      loot: null,
      am_i_affected: t("Rien ne le prouve pour l'instant.", 'Nothing proves it so far.'),
      action: t('Ne cliquez sur aucun lien qui accompagne cette rumeur.', 'Do not click any link that comes with this rumour.'),
      summary: [
        t(
          "Un compte anonyme sur X affirme détenir des données de clients d'Ondalis et propose de les vendre. Aucune preuve n'a été publiée, et Ondalis n'a pas réagi.",
          'An anonymous account on X claims to hold data of Ondalis customers and offers to sell it. No proof has been published, and Ondalis has not reacted.',
        ),
        t(
          "Cette fiche existe pour vous éviter les arnaques qui profitent des rumeurs. Elle sera mise à jour dès qu'une source fiable se prononcera.",
          'This card exists to spare you the scams that feed on rumours. It will be updated as soon as a reliable source speaks.',
        ),
      ],
      timeline: [
        { date: ago(2), label: t('Message publié sur X', 'Message posted on X') },
        { date: ago(1.2), label: t('Repris par quelques comptes', 'Picked up by a few accounts') },
        { date: ago(0.75), label: t('Fiche ouverte, en attente de confirmation', 'Card opened, waiting for confirmation') },
      ],
      protection_steps: [
        t('Ne cliquez sur aucun lien partagé autour de cette rumeur.', 'Do not click any link shared around this rumour.'),
        t('Ne téléchargez rien de présenté comme des « données volées ».', 'Do not download anything presented as “stolen data”.'),
      ],
      technical: { cves: [], software: [], techniques: [] },
      sources: [{ name: 'X', title: fictional("Message d'un compte anonyme", 'Message from an anonymous account'), url: null, official: false }],
    },
    {
      id: 'test-faux-rib',
      severity: 'significative',
      severity_reason: t("Une centaine d'entreprises touchées, sans fuite de données.", 'About a hundred companies hit, without a data leak.'),
      title: t('De faux fournisseurs envoient de faux RIB à des PME', 'Fake suppliers send fake bank details to small businesses'),
      lede: t(
        "Les escrocs piratent la messagerie d'un fournisseur, puis annoncent à ses clients un changement de banque.",
        'The fraudsters hack a supplier’s mailbox, then tell its customers about a change of bank.',
      ),
      first_seen: dayAt(1, '16:30'),
      sector: t('Entreprises', 'Businesses'),
      audience: 'entreprises',
      reliability: 'confirme',
      attacker: unknownAttacker,
      victim: { label: t('Une centaine de PME', 'About a hundred small businesses'), status: 'confirme' },
      method: t('Messagerie de fournisseur piratée', 'Supplier mailbox hacked'),
      loot: t("Virements détournés, jusqu'à 80 000 €", 'Diverted transfers, up to €80,000'),
      am_i_affected: t('Oui, si un fournisseur vous a annoncé un nouveau RIB par e-mail.', 'Yes, if a supplier told you about new bank details by e-mail.'),
      action: t('Appelez-le au numéro habituel avant tout virement.', 'Call them on the usual number before any transfer.'),
      summary: [
        t(
          'Les escrocs prennent le contrôle de la messagerie de petits fournisseurs, puis écrivent à leurs clients pour annoncer un changement de banque.',
          'The fraudsters take control of the mailbox of small suppliers, then write to their customers to announce a change of bank.',
        ),
        t(
          "Les virements partent vers leurs comptes. Une centaine de PME l'ont signalé cette semaine.",
          'The transfers go to their accounts. About a hundred small businesses reported it this week.',
        ),
      ],
      timeline: [
        { date: dayAt(4, '09:00'), label: t('Premières plaintes de PME', 'First complaints from small businesses') },
        { date: dayAt(2, '14:00'), label: t('Mode opératoire identifié', 'Method identified') },
        { date: dayAt(1, '16:30'), label: t('Alerte de la préfecture aux entreprises', 'Alert from the prefecture to businesses') },
      ],
      protection_steps: [
        t('Confirmez par téléphone, au numéro habituel, tout changement de RIB.', 'Confirm any change of bank details by phone, on the usual number.'),
        t('Faites valider par deux personnes tout virement inhabituel.', 'Have any unusual transfer approved by two people.'),
      ],
      technical: {
        cves: [],
        software: [t('Messageries des fournisseurs', 'Suppliers’ mailboxes')],
        techniques: [
          { id: 'T1534', name: 'Internal Spearphishing' },
          { id: 'T1657', name: 'Financial Theft' },
        ],
      },
      sources: [{ name: 'Préfecture de Rives-Ouest', title: fictional('Alerte aux entreprises', 'Alert to businesses'), url: null, official: true }],
    },
    {
      id: 'test-vendalo',
      severity: 'significative',
      severity_reason: t('Entre 1 000 et 100 000 personnes, sans donnée sensible.', 'Between 1,000 and 100,000 people, without sensitive data.'),
      title: t('12 000 comptes Vendalo piratés avec des mots de passe réutilisés', '12,000 Vendalo accounts hacked with reused passwords'),
      lede: t(
        "Des identifiants volés sur d'autres sites ont ouvert 12 000 comptes clients de la marketplace.",
        'Credentials stolen on other sites opened 12,000 customer accounts of the marketplace.',
      ),
      first_seen: dayAt(2, '08:15'),
      sector: t('E-commerce', 'E-commerce'),
      audience: 'grand_public',
      reliability: 'confirme',
      attacker: null,
      victim: { label: t('12 000 clients de Vendalo', '12,000 Vendalo customers'), status: 'confirme' },
      method: t('Anciens mots de passe testés en masse', 'Old passwords tried in bulk'),
      loot: t('Adresses, commandes, points de fidélité', 'Addresses, orders, loyalty points'),
      am_i_affected: t('Oui, si Vendalo vous a demandé de changer de mot de passe.', 'Yes, if Vendalo asked you to change your password.'),
      action: t("Changez ce mot de passe partout où vous l'utilisiez.", 'Change this password everywhere you used it.'),
      summary: [
        t(
          "Des pirates ont essayé sur Vendalo des millions d'identifiants volés ailleurs. Ils sont entrés dans 12 000 comptes dont le mot de passe servait aussi sur un autre site.",
          'Attackers tried millions of credentials stolen elsewhere on Vendalo. They got into 12,000 accounts whose password was also used on another site.',
        ),
        t(
          'Ils ont vu les adresses et les commandes, et dépensé des points de fidélité. Les cartes bancaires ne sont pas enregistrées chez Vendalo.',
          'They saw addresses and orders, and spent loyalty points. Bank cards are not stored at Vendalo.',
        ),
      ],
      timeline: [
        { date: dayAt(3, '23:10'), label: t('Pic de connexions inhabituelles', 'Peak of unusual logins') },
        { date: dayAt(2, '06:30'), label: t('Comptes touchés bloqués', 'Affected accounts blocked') },
        { date: dayAt(2, '08:15'), label: t('E-mail aux clients concernés', 'E-mail to the customers concerned') },
      ],
      protection_steps: [
        t('Changez votre mot de passe Vendalo.', 'Change your Vendalo password.'),
        t("Changez-le aussi partout où vous l'utilisiez.", 'Change it too everywhere you used it.'),
      ],
      technical: { cves: [], software: [t('Espace client Vendalo', 'Vendalo customer area')], techniques: [{ id: 'T1110.004', name: 'Credential Stuffing' }] },
      sources: [{ name: 'Vendalo', title: fictional('E-mail aux clients', 'E-mail to customers'), url: null, official: true }],
    },
    {
      id: 'test-morvalene',
      severity: 'mineure',
      severity_reason: t('Une seule petite structure, touchée quelques heures.', 'A single small organisation, hit for a few hours.'),
      title: t('Le site de la mairie de Morvalène défiguré trois heures', 'The Morvalène town hall website defaced for three hours'),
      lede: t(
        "La page d'accueil a été remplacée par un message, puis le site a été remis en ligne.",
        'The home page was replaced by a message, then the site was put back online.',
      ),
      first_seen: ago(3.4),
      sector: t('Collectivité', 'Local authority'),
      audience: 'grand_public',
      reliability: 'confirme',
      attacker: { name: t('Collectif Brisant', 'Brisant collective'), country: null, status: 'revendique', source: null },
      victim: { label: t('Site web de la mairie', 'Town hall website'), status: 'confirme' },
      method: t('Extension du site jamais mise à jour', 'Site extension never updated'),
      loot: t("Page d'accueil remplacée, aucune donnée volée", 'Home page replaced, no data stolen'),
      am_i_affected: t("Non, aucune donnée personnelle n'a été touchée.", 'No, no personal data was touched.'),
      action: t("Passez par l'adresse habituelle du site pour vos démarches.", 'Use the usual address of the site for your procedures.'),
      summary: [
        t(
          "La page d'accueil du site de Morvalène a été remplacée pendant trois heures par un message du collectif Brisant.",
          'The home page of the Morvalène website was replaced for three hours by a message from the Brisant collective.',
        ),
        t(
          "Le site a été remis en ligne dans la journée. Aucune donnée personnelle n'y était stockée.",
          'The site was put back online during the day. No personal data was stored on it.',
        ),
      ],
      timeline: [
        { date: ago(6.4), label: t("Page d'accueil remplacée", 'Home page replaced') },
        { date: ago(4.8), label: t('Site coupé par la mairie', 'Site taken down by the town hall') },
        { date: ago(3.4), label: t('Site remis en ligne', 'Site back online') },
      ],
      protection_steps: [t("N'ouvrez pas les liens qui figuraient sur la page piratée.", 'Do not open the links that were on the hacked page.')],
      technical: { cves: [], software: [t('Extension de formulaire du site', 'Form extension of the site')], techniques: [{ id: 'T1491.002', name: 'External Defacement' }] },
      sources: [{ name: 'Mairie de Morvalène', title: fictional('Message aux habitants', 'Message to residents'), url: null, official: true }],
    },
    {
      id: 'test-photoluxe',
      severity: 'mineure',
      severity_reason: t('Moins de 1 000 personnes touchées.', 'Fewer than 1,000 people hit.'),
      title: t('Une fausse appli de retouche photo vole des mots de passe sur Mac', 'A fake photo editing app steals passwords on Mac'),
      lede: t(
        "« PhotoLuxe », diffusée par des publicités, copie les mots de passe enregistrés sur l'ordinateur.",
        '“PhotoLuxe”, spread through ads, copies the passwords saved on the computer.',
      ),
      first_seen: dayAt(2, '11:20'),
      sector: t('Logiciel', 'Software'),
      audience: 'grand_public',
      reliability: 'confirme',
      attacker: unknownAttacker,
      victim: { label: t('Quelques centaines de Mac', 'A few hundred Macs'), status: 'confirme' },
      method: t('Fausse appli gratuite installée par publicité', 'Fake free app installed through ads'),
      loot: t('Mots de passe enregistrés', 'Saved passwords'),
      am_i_affected: t("Oui, si vous avez installé « PhotoLuxe » hors de l'App Store.", 'Yes, if you installed “PhotoLuxe” outside the App Store.'),
      action: t("Supprimez l'appli et changez vos mots de passe importants.", 'Delete the app and change your important passwords.'),
      summary: [
        t(
          '« PhotoLuxe », une fausse appli de retouche diffusée par des publicités, copie les mots de passe enregistrés sur le Mac.',
          '“PhotoLuxe”, a fake editing app spread through ads, copies the passwords saved on the Mac.',
        ),
        t(
          "Quelques centaines d'installations sont recensées. L'appli n'a jamais été proposée sur l'App Store.",
          'A few hundred installations are recorded. The app was never offered on the App Store.',
        ),
      ],
      timeline: [
        { date: dayAt(5, '10:00'), label: t('Premières publicités repérées', 'First ads spotted') },
        { date: dayAt(3, '15:30'), label: t("Analyse de l'appli publiée", 'Analysis of the app published') },
        { date: dayAt(2, '11:20'), label: t('Alerte aux utilisateurs de Mac', 'Alert to Mac users') },
      ],
      protection_steps: [
        t("Supprimez « PhotoLuxe » si vous l'avez installée.", 'Delete “PhotoLuxe” if you installed it.'),
        t('Changez les mots de passe de votre messagerie et de votre banque.', 'Change the passwords of your mailbox and your bank.'),
      ],
      technical: { cves: [], software: [t('« PhotoLuxe », toutes versions', '“PhotoLuxe”, all versions')], techniques: [{ id: 'T1555.001', name: 'Keychain' }] },
      sources: [{ name: 'CERT-FR', title: fictional('Alerte sur une fausse appli', 'Alert on a fake app'), url: null, official: true }],
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
      severity_reason: t('Une panne de quelques heures, sans vol de données.', 'An outage of a few hours, without data theft.'),
      title: t("L'application des transports Trameo coupée deux heures", 'The Trameo transport app down for two hours'),
      lede: t(
        "Un afflux de fausses connexions a saturé l'application, sans que personne n'y entre.",
        'A flood of fake connections overloaded the app, without anyone getting in.',
      ),
      first_seen: ago(2.4),
      sector: t('Transport', 'Transport'),
      audience: 'grand_public',
      reliability: 'confirme',
      attacker: unknownAttacker,
      victim: { label: t('Application des transports Trameo', 'Trameo transport app'), status: 'confirme' },
      method: t('Afflux de fausses connexions', 'Flood of fake connections'),
      loot: t('Service coupé, aucune donnée volée', 'Service down, no data stolen'),
      am_i_affected: t('Non, sauf pour acheter un titre pendant la panne.', 'No, except to buy a ticket during the outage.'),
      action: t("Rien à faire : l'application fonctionne de nouveau.", 'Nothing to do: the app works again.'),
      summary: [
        t(
          "L'application du réseau Trameo a reçu un flot de fausses connexions qui l'a rendue inaccessible pendant deux heures.",
          'The Trameo network app received a flood of fake connections that made it unreachable for two hours.',
        ),
        t(
          "Aucune donnée n'a été volée : ce type d'attaque bloque un service sans y entrer.",
          'No data was stolen: this kind of attack blocks a service without getting into it.',
        ),
      ],
      timeline: [
        { date: ago(4.5), label: t('Application inaccessible', 'App unreachable') },
        { date: ago(3.2), label: t("Trafic filtré par l'hébergeur", 'Traffic filtered by the host') },
        { date: ago(2.4), label: t('Retour à la normale', 'Back to normal') },
      ],
      protection_steps: [t("Achetez vos titres dans l'application officielle, comme d'habitude.", 'Buy your tickets in the official app, as usual.')],
      technical: { cves: [], software: [], techniques: [{ id: 'T1498', name: 'Network Denial of Service' }] },
      sources: [{ name: 'Trameo', title: fictional('Message aux voyageurs', 'Message to travellers'), url: null, official: true }],
    },
    day.find((attack) => attack.id === 'test-morvalene'),
    {
      id: 'test-valtorre',
      severity: 'mineure',
      severity_reason: t('Moins de 1 000 personnes visées, sans intrusion.', 'Fewer than 1,000 people targeted, without intrusion.'),
      title: t("Un faux concours au nom de l'AS Valtorre circule", 'A fake contest in the name of AS Valtorre is going round'),
      lede: t('Un faux compte du club promet un maillot contre des « frais de port ».', 'A fake account of the club promises a shirt against “postage fees”.'),
      first_seen: dayAt(1, '18:10'),
      sector: t('Sport', 'Sport'),
      audience: 'grand_public',
      reliability: 'confirme',
      attacker: unknownAttacker,
      victim: { label: t('Supporters du club', 'Club supporters'), status: 'confirme' },
      method: t('Faux compte imitant celui du club', 'Fake account imitating the club’s'),
      loot: t('Quelques coordonnées bancaires', 'A few bank details'),
      am_i_affected: t('Oui, si vous avez joué au concours « maillot offert ».', 'Yes, if you entered the “free shirt” contest.'),
      action: t('Faites opposition si vous avez donné votre carte.', 'Block your card if you gave it.'),
      summary: [
        t(
          "Un faux compte imitant celui de l'AS Valtorre promet un maillot offert contre des frais de port. Le club n'organise aucun concours.",
          'A fake account imitating that of AS Valtorre promises a free shirt against postage fees. The club runs no contest.',
        ),
        t('Le compte a été suspendu. Quelques centaines de personnes ont participé.', 'The account has been suspended. A few hundred people took part.'),
      ],
      timeline: [
        { date: dayAt(2, '20:00'), label: t('Faux compte créé', 'Fake account created') },
        { date: dayAt(1, '12:00'), label: t('Premiers signalements de supporters', 'First reports from supporters') },
        { date: dayAt(1, '18:10'), label: t('Démenti du club', 'Denial from the club') },
      ],
      protection_steps: [
        t('Faites opposition si vous avez donné votre carte.', 'Block your card if you gave it.'),
        t('Ne suivez que le compte officiel du club.', 'Follow only the official account of the club.'),
      ],
      technical: { cves: [], software: [], techniques: [{ id: 'T1585.001', name: 'Social Media Accounts' }] },
      sources: [{ name: 'AS Valtorre', title: fictional('Démenti officiel', 'Official denial'), url: null, official: true }],
    },
  ];
}

// Critical alerts that a test adds on top of the usual day, one by one.
const ALERTS = [
  {
    id: 'test-ferlino',
    source: 'Ferlino',
    severity_reason: t("Un service vital (transport) paralysé à l'échelle d'une région.", 'A vital service (transport) paralysed across a region.'),
    title: t('Les trains régionaux Ferlino arrêtés par un rançongiciel', 'Ferlino regional trains stopped by ransomware'),
    lede: t(
      'Les serveurs qui règlent la circulation sont bloqués : les trains sont arrêtés sur 14 lignes.',
      'The servers that manage the traffic are blocked: trains are stopped on 14 lines.',
    ),
    sector: t('Transport', 'Transport'),
    victim: { label: t('120 000 voyageurs par jour', '120,000 travellers a day'), status: 'confirme' },
    method: t('Rançongiciel sur les serveurs de régulation', 'Ransomware on the traffic control servers'),
    loot: t('Circulation suspendue sur 14 lignes', 'Traffic suspended on 14 lines'),
    am_i_affected: t("Oui, si vous prenez un train Ferlino aujourd'hui.", 'Yes, if you take a Ferlino train today.'),
    action: t("Vérifiez votre trajet dans l'application avant de partir.", 'Check your journey in the app before leaving.'),
    summary: [
      t(
        'Un rançongiciel a bloqué les serveurs qui règlent la circulation du réseau régional Ferlino. Par sécurité, les trains sont arrêtés sur 14 lignes.',
        'Ransomware blocked the servers that manage the traffic of the Ferlino regional network. For safety, trains are stopped on 14 lines.',
      ),
      t(
        "Aucun groupe n'a revendiqué l'attaque. Ferlino annonce une reprise progressive dans la soirée.",
        'No group has claimed the attack. Ferlino announces a gradual restart in the evening.',
      ),
    ],
    steps: [
      [1.5, t('Pannes en cascade sur la régulation', 'Cascading failures in traffic control')],
      [0.7, t('Circulation suspendue par précaution', 'Traffic suspended as a precaution')],
      [0, t('Alerte publique de Ferlino', 'Public alert from Ferlino')],
    ],
    protection_steps: [
      t("Vérifiez votre trajet dans l'application avant de partir.", 'Check your journey in the app before leaving.'),
      t('Gardez votre billet : les trajets annulés seront remboursés.', 'Keep your ticket: cancelled journeys will be refunded.'),
    ],
    techniques: [{ id: 'T1486', name: 'Data Encrypted for Impact' }],
  },
  {
    id: 'test-valmeuse',
    source: 'Eaux de Valmeuse',
    severity_reason: t("Un service vital (l'eau) touché.", 'A vital service (water) hit.'),
    title: t("Des pirates ont pris la main sur le réseau d'eau de Valmeuse", 'Attackers took control of the Valmeuse water network'),
    lede: t(
      'Ils sont entrés par un accès à distance oublié ; les équipes sont passées en commande manuelle.',
      'They got in through a forgotten remote access; the teams switched to manual control.',
    ),
    sector: t('Eau', 'Water'),
    victim: { label: t('310 000 habitants', '310,000 residents'), status: 'confirme' },
    method: t('Accès à distance oublié, mot de passe par défaut', 'Forgotten remote access, default password'),
    loot: t('Pompes pilotées à distance, coupures', 'Pumps controlled remotely, outages'),
    am_i_affected: t('Oui, si vous habitez la métropole de Valmeuse.', 'Yes, if you live in the Valmeuse metropolitan area.'),
    action: t('Suivez uniquement les consignes officielles de la mairie.', 'Follow only the official instructions of the town hall.'),
    summary: [
      t(
        "Des pirates ont pris le contrôle de pompes du réseau d'eau de Valmeuse grâce à un accès à distance oublié. Les équipes ont repris la main en passant en commande manuelle.",
        'Attackers took control of pumps of the Valmeuse water network through a forgotten remote access. The teams took back control by switching to manual operation.',
      ),
      t(
        "L'eau reste potable selon l'exploitant. Des coupures ponctuelles sont possibles dans la journée.",
        'The water stays drinkable according to the operator. Occasional cuts are possible during the day.',
      ),
    ],
    steps: [
      [3, t('Commandes anormales sur des pompes', 'Abnormal commands on pumps')],
      [1, t('Passage en commande manuelle', 'Switch to manual control')],
      [0, t("Alerte de l'exploitant", 'Alert from the operator')],
    ],
    protection_steps: [
      t('Suivez uniquement les consignes officielles de la mairie.', 'Follow only the official instructions of the town hall.'),
      t("Gardez quelques bouteilles d'eau en réserve aujourd'hui.", 'Keep a few bottles of water in reserve today.'),
    ],
    techniques: [{ id: 'T0822', name: 'External Remote Services' }],
  },
  {
    id: 'test-monetis',
    source: 'Monétis',
    severity_reason: t(
      'Un impact national : le paiement par carte bloqué dans des milliers de magasins.',
      'A national impact: card payment blocked in thousands of shops.',
    ),
    title: t('Le paiement par carte bloqué dans 8 000 magasins', 'Card payment blocked in 8,000 shops'),
    lede: t(
      'Les serveurs du réseau Monétis, qui valide les paiements, sont hors ligne depuis ce matin.',
      'The servers of the Monétis network, which approves payments, have been offline since this morning.',
    ),
    sector: t('Paiement', 'Payment'),
    victim: { label: t('8 000 magasins', '8,000 shops'), status: 'confirme' },
    method: t('Serveurs de paiement saturés', 'Payment servers overloaded'),
    loot: t('Paiements par carte impossibles', 'Card payments impossible'),
    am_i_affected: t('Oui, si votre magasin habituel passe par Monétis.', 'Yes, if your usual shop goes through Monétis.'),
    action: t("Gardez un autre moyen de paiement sur vous aujourd'hui.", 'Keep another means of payment on you today.'),
    summary: [
      t(
        'Les serveurs du réseau Monétis, qui valide les paiements par carte de 8 000 magasins, sont hors ligne depuis le matin après une attaque.',
        'The servers of the Monétis network, which approves card payments for 8,000 shops, have been offline since the morning after an attack.',
      ),
      t(
        "Aucune donnée bancaire n'aurait été volée. Le retour à la normale est attendu dans la journée.",
        'No banking data is said to have been stolen. A return to normal is expected during the day.',
      ),
    ],
    steps: [
      [2.5, t('Premiers refus de paiement', 'First payment refusals')],
      [1, t('Serveurs mis hors ligne', 'Servers taken offline')],
      [0, t('Communiqué de Monétis', 'Statement from Monétis')],
    ],
    protection_steps: [
      t("Gardez un autre moyen de paiement sur vous aujourd'hui.", 'Keep another means of payment on you today.'),
      t('Méfiez-vous des SMS « de remboursement » liés à la panne.', 'Be wary of “refund” text messages linked to the outage.'),
    ],
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
    kind: 'attaque',
    severity: 'critique',
    first_seen: ago(0),
    audience: 'les_deux',
    reliability: 'confirme',
    attacker: unknownAttacker,
    timeline: steps.map(([hours, label]) => ({ date: ago(hours), label })),
    technical: { cves: [], software: [], techniques },
    sources: [{ name: source, title: fictional('Communiqué officiel', 'Official statement'), url: null, official: true }],
  };
}

/** The test cards about a flaw; the others are attacks. */
const FLAWS = new Set(['test-amperys']);

/** A test feed, as the collector would write it: the usual day, or a calm one. */
export function buildFeed(now, { calm = false } = {}) {
  return {
    generated_at: new Date(now - 12 * 60_000).toISOString(),
    attacks: (calm ? calmDay(now) : usualDay(now)).map((card) => ({ ...card, kind: FLAWS.has(card.id) ? 'faille' : 'attaque' })),
  };
}

/** Names invented for these feeds: none of them may ever appear in the built site. */
export const INVENTED_NAMES = [
  'TelecomX', 'Ondalis', 'Vendalo', 'PhotoLuxe', 'Trameo', 'Valtorre', 'Ferlino', 'Valmeuse',
  'Kovalt', 'Vantor', 'Morval', 'Ampérys', 'Monétis', 'Rives-Ouest', 'test-telecomx',
];
