# Documentation EYWAI

Pour installer et lancer un poste : [reference/demarrage.md](reference/demarrage.md).
Architecture du code : [../ARCHITECTURE.md](../ARCHITECTURE.md).

## Dossiers

- `reference/` : ce qui décrit le système aujourd'hui. Tenu à jour.
- `decisions/adr/` : les décisions d'architecture (ADR).
- `comptes-rendus/` : audits, réunions, questions, rapprochements, revues. Un
  fichier daté par sujet, `AAAA-MM-JJ-sujet.md`, qui décrit ce jour-là.
- `archive/` : ce qui n'est plus vrai, gardé pour mémoire.
- `superpowers/` : les specs (`specs/`) et les plans (`plans/`) des chantiers.
- `commercial/` : documents commerciaux (Word).
- `backtest/` : journaux de backtest, sur le poste seulement (ignoré par git).

## Références

- [demarrage.md](reference/demarrage.md) : installer, lancer, tester, règles du dépôt.
- [guide-environnement-test.md](reference/guide-environnement-test.md) : le site de test, la resynchro, les migrations.
- [bascule-production.md](reference/bascule-production.md) : faire de la base de test la production.
- La reprise de paie Colorplast (état et règles) et les rapprochements ligne à
  ligne nomment des salariés : ils vivent hors git, sous
  `data/colorplast/referentiel/` et `data/colorplast/rapprochements/`.
- [donnees-locales.md](reference/donnees-locales.md) : où ranger les données de paie, sous `data/`.
- [strategie-qa.md](reference/strategie-qa.md) : QA exploratoire, tests Playwright, smoke.
- [net-entreprises-missions.md](reference/net-entreprises-missions.md) : net-entreprises et dépôt des DSN.
- [fiches-parametrage-oc.md](reference/fiches-parametrage-oc.md) : fiches des organismes complémentaires.
- [colorplast-primes.md](reference/colorplast-primes.md) : primes Colorplast, guide RH.
- [primes-equipes-planning.md](reference/primes-equipes-planning.md) : primes d'équipes et planning, guide RH.
