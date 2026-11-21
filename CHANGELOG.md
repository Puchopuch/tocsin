# Changelog

The changes of Tocsin, newest first. Versions follow [Semantic Versioning](https://semver.org/).
*En français : plus bas, sous chaque version.*

## [1.0.0](https://github.com/Puchopuch/tocsin/releases/tag/v1.0.0) (2026-11-21)

First public release.

### What it does

- **A collector** (Python 3.12) reads reliable sources and writes `frontend/public/data/cards.json`:
  one card per exploited flaw or attack of the last seven days, in French and in English, each
  with its sources. `check-sources` tests the sources and the keys, `run` collects, `validate`
  checks the existing `cards.json`.
- **Without any key**: the CISA catalogue of exploited flaws (KEV) and the alerts of the CERT-FR.
  Their cards are written without AI, from fixed tables: the type of flaw (CWE, or name given by
  the CISA); the consequence found in the text of the source, otherwise "Not disclosed"; "Used by
  ransomware, according to the CISA" when the CISA says so; for the CERT-FR, the targets and the
  impact from the "Systèmes affectés" and "Risques" of the alert.
- **With a Mistral key** (optional): the articles of BleepingComputer, The Record, ZATAZ and
  LeMagIT, read by an AI that never judges. Each fact needs a quote found word for word in the
  article; the code sets the level; the second call receives only the verified facts, never the
  article; a text holding a link, an e-mail, a phone number, an IBAN, a wallet address or a number
  absent from the facts is refused. The CISA texts are translated into French. At most 40 calls
  per run, dated model `mistral-small-2603`; every card written or translated by the AI says so on
  the card itself.
- **With a ransomware.live key** (optional): ransomware claims against organisations in France,
  shown as "Claimed, not confirmed", never above "Significant".
- **Duplicates merged**: the same CVE, or the same victim within 7 days, make one card with all its
  sources.
- **The site** (React, Vite), in French and in English: the cards of the last seven days, a
  sentence for the day, and for each card its level, its method and its sources. Its emblem, a
  discreet watermark, is a dragon of Ulisse Aldrovandi (1640, public domain).

### Security

- Requests: https only, to the listed sites only, at public addresses only (checked after DNS, at
  each redirect and on the connection), TLS always verified, time and size limits, compression
  bombs stopped.
- Inputs: XML without DTD (defusedxml), broken entries skipped, hidden characters removed, SQLite
  queries with placeholders.
- Keys: secret values, sent to their own API only, never logged. A missing or refused key skips its
  source with a clear message; `check-sources` says "absente", "valide" or "refusée", never the
  key.
- Site: a strict Content-Security-Policy, Trusted Types, links checked again, no request to
  another site.
- On every push, without any key: pytest, `npm run check`, gitleaks, pip-audit, `npm audit` and
  Bandit; Dependabot for pip, npm and GitHub Actions. See [SECURITY.md](SECURITY.md).

### Known limits

- Tocsin is not an official service: always check the source before acting.
- The parts that need a key, Mistral and ransomware.live, are tested with simulated answers only:
  no test ever called the real services.
- The data are those of the last collection, not live.
- "Tocsin" is a provisional name.

### En français

Première version publique.

**Ce que fait Tocsin**

- **Un collecteur** (Python 3.12) lit des sources fiables et écrit
  `frontend/public/data/cards.json` : une fiche par faille exploitée ou par attaque des sept
  derniers jours, en français et en anglais, chacune avec ses sources. `check-sources` teste les
  sources et les clés, `run` collecte, `validate` contrôle le `cards.json` existant.
- **Sans aucune clé** : le catalogue des failles exploitées de la CISA (KEV) et les alertes du
  CERT-FR. Leurs fiches sont écrites sans IA, à partir de tables fixes : le type de faille (CWE,
  ou nom donné par la CISA) ; la conséquence trouvée dans le texte de la source, sinon « Non
  communiqué » ; « Utilisée par des rançongiciels, selon la CISA » quand la CISA le dit ; pour le
  CERT-FR, les cibles et l'impact tirés des rubriques « Systèmes affectés » et « Risques » de
  l'alerte.
- **Avec une clé Mistral** (facultative) : les articles de BleepingComputer, The Record, ZATAZ et
  LeMagIT, lus par une IA qui ne juge jamais. Chaque fait exige une citation trouvée mot pour mot
  dans l'article ; le code fixe le niveau ; le second appel ne reçoit que les faits vérifiés,
  jamais l'article ; un texte qui contient un lien, un e-mail, un numéro de téléphone, un IBAN, une
  adresse de portefeuille ou un nombre absent des faits est refusé. Les textes de la CISA sont
  traduits en français. 40 appels au plus par collecte, modèle daté `mistral-small-2603` ; chaque
  fiche rédigée ou traduite par l'IA le dit sur la fiche elle-même.
- **Avec une clé ransomware.live** (facultative) : les revendications de rançongiciels contre des
  organisations en France, affichées « Revendiqué, non confirmé », jamais au-dessus de
  « Significative ».
- **Doublons fusionnés** : la même CVE, ou la même victime à 7 jours près, donnent une seule fiche
  avec toutes ses sources.
- **Le site** (React, Vite), en français et en anglais : les fiches des sept derniers jours, une
  phrase du jour, et pour chaque fiche son niveau, sa méthode et ses sources. Son emblème, en
  filigrane discret, est un dragon d'Ulisse Aldrovandi (1640, domaine public).

**Sécurité**

- Requêtes : https seulement, vers les sites prévus seulement, à des adresses publiques seulement
  (vérifiées après le DNS, à chaque redirection et sur la connexion), TLS toujours vérifié,
  limites de temps et de taille, bombes de compression arrêtées.
- Entrées : XML sans DTD (defusedxml), entrées cassées écartées, caractères cachés retirés,
  requêtes SQLite avec des paramètres.
- Clés : valeurs secrètes, envoyées à leur propre API seulement, jamais journalisées. Une clé
  absente ou refusée fait sauter sa source avec un message clair ; `check-sources` dit
  « absente », « valide » ou « refusée », jamais la clé.
- Site : une Content-Security-Policy stricte, Trusted Types, liens revérifiés, aucune requête vers
  un autre site.
- À chaque push, sans aucune clé : pytest, `npm run check`, gitleaks, pip-audit, `npm audit` et
  Bandit ; Dependabot pour pip, npm et GitHub Actions. Voir [SECURITY.md](SECURITY.md).

**Limites connues**

- Tocsin n'est pas un service officiel : vérifiez toujours la source avant d'agir.
- Les parties qui demandent une clé, Mistral et ransomware.live, ne sont testées qu'avec des
  réponses simulées : aucun test n'a jamais appelé les vrais services.
- Les données sont celles de la dernière collecte, pas du direct.
- « Tocsin » est un nom provisoire.
