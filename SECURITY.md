# Security policy

*[Version française plus bas](#politique-de-sécurité)*

## Report a vulnerability

Report it **privately**, through GitHub:
[Report a vulnerability](https://github.com/Puchopuch/tocsin/security/advisories/new) (the
**Security** tab of the repository, then **Report a vulnerability**). Never in a public issue, a
pull request or a discussion. There is no e-mail address for this: a private report reaches the
maintainer only.

Please say:

- what is affected: the collector, the site or the CI, and the version or the commit;
- how to reproduce it, with the smallest example you can;
- what an attacker could do with it.

**Never send a real key**, not even yours: a fake one shows the problem just as well. If a key of
yours leaked, delete it at its provider and create a new one (README, "Keys, step by step").

Tocsin is maintained on free time: expect a first answer within 14 days. A fix is published with a
GitHub security advisory, which credits you if you wish.

## Supported versions

Only the latest release, and the `main` branch, get security fixes.

## Scope

In scope:

- **the collector**: its requests (allowed sites, public addresses, TLS, redirects, time and size
  limits), the reading of the sources (XML, JSON, HTML), the handling of the keys, the checks of
  the answers of the AI (schema, quotes, links and numbers refused), `state.db` and `cards.json`;
- **the site**: anything that would run a script, inject content or a link coming from
  `cards.json`, or send a request to another site; its Content-Security-Policy;
- **the CI workflow** of this repository.

Out of scope:

- an error in a source (the CISA, the CERT-FR, the press, ransomware.live): tell the source; a card
  that repeats it is not a flaw of Tocsin;
- the services themselves: Mistral, ransomware.live, GitHub;
- an attack that needs control of the computer that runs the collector, or of its `.env`;
- the hosting of a copy of the site that you deploy yourself (its HTTP headers are yours to set).

## What is tested

On every push to `main` and every pull request, GitHub Actions runs, without any key or secret,
with read-only rights and actions pinned by commit:

- `pytest`: requests (allowed sites, private and metadata addresses, redirects, TLS, time limits,
  compression bombs), inputs (XXE, billion laughs, broken files, hidden characters, dangerous
  links, SQL), keys (never in a log, an error, `state.db` or `cards.json`), resilience, and press
  articles trapped against the AI, with simulated answers;
- `npm run check`: the site, built then driven in a browser: XSS attempts in every field, the CSP,
  Trusted Types, the links, requests to other sites, broken or huge data;
- gitleaks on the whole history; pip-audit and `npm audit` on the dependencies; Bandit on the
  collector.

Dependabot proposes the updates of pip, npm and GitHub Actions. The parts that need a key, Mistral
and ransomware.live, are tested with simulated answers only.

---

# Politique de sécurité

## Signaler une faille

Signalez-la **en privé**, par GitHub :
[Report a vulnerability](https://github.com/Puchopuch/tocsin/security/advisories/new) (l'onglet
**Security** du dépôt, puis **Report a vulnerability**). Jamais dans une issue publique, une pull
request ou une discussion. Il n'y a pas d'adresse e-mail pour cela : un signalement privé n'arrive
qu'au mainteneur.

Indiquez :

- ce qui est touché : le collecteur, le site ou la CI, et la version ou le commit ;
- comment le reproduire, avec l'exemple le plus petit possible ;
- ce qu'un attaquant pourrait en faire.

**N'envoyez jamais une vraie clé**, même la vôtre : une fausse montre le problème tout aussi bien.
Si l'une de vos clés a fuité, supprimez-la chez son fournisseur et créez-en une nouvelle (README,
« Les clés, pas à pas »).

Tocsin est maintenu sur du temps libre : comptez une première réponse sous 14 jours. Une correction
est publiée avec un avis de sécurité GitHub, qui vous cite si vous le souhaitez.

## Versions suivies

Seules la dernière version publiée et la branche `main` reçoivent des corrections de sécurité.

## Périmètre

Dans le périmètre :

- **le collecteur** : ses requêtes (sites autorisés, adresses publiques, TLS, redirections, limites
  de temps et de taille), la lecture des sources (XML, JSON, HTML), le traitement des clés, les
  contrôles des réponses de l'IA (schéma, citations, liens et numéros refusés), `state.db` et
  `cards.json` ;
- **le site** : tout ce qui ferait exécuter un script, injecter un contenu ou un lien venu de
  `cards.json`, ou envoyer une requête à un autre site ; sa Content-Security-Policy ;
- **le workflow de CI** de ce dépôt.

Hors périmètre :

- une erreur d'une source (la CISA, le CERT-FR, la presse, ransomware.live) : signalez-la à la
  source ; une fiche qui la reprend n'est pas une faille de Tocsin ;
- les services eux-mêmes : Mistral, ransomware.live, GitHub ;
- une attaque qui demande de contrôler l'ordinateur qui fait tourner le collecteur, ou son `.env` ;
- l'hébergement d'une copie du site que vous déployez vous-même (ses en-têtes HTTP sont à régler de
  votre côté).

## Ce qui est testé

À chaque push sur `main` et à chaque pull request, GitHub Actions lance, sans clé ni secret, avec
des droits en lecture seule et des actions épinglées par commit :

- `pytest` : les requêtes (sites autorisés, adresses privées et de métadonnées, redirections, TLS,
  délais, bombes de compression), les entrées (XXE, billion laughs, fichiers cassés, caractères
  cachés, liens dangereux, SQL), les clés (jamais dans un journal, une erreur, `state.db` ni
  `cards.json`), la résilience, et des articles de presse piégés contre l'IA, avec des réponses
  simulées ;
- `npm run check` : le site, construit puis parcouru dans un navigateur : tentatives de XSS dans
  chaque champ, CSP, Trusted Types, liens, requêtes vers d'autres sites, données cassées ou
  énormes ;
- gitleaks sur tout l'historique ; pip-audit et `npm audit` sur les dépendances ; Bandit sur le
  collecteur.

Dependabot propose les mises à jour de pip, npm et GitHub Actions. Les parties qui demandent une
clé, Mistral et ransomware.live, ne sont testées qu'avec des réponses simulées.
