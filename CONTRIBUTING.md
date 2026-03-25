# Contribuer au dépôt EYWAI

**Première fois sur le projet ?** Voir **[GUIDE_UTILISATION.md](GUIDE_UTILISATION.md)** (installation, Git, hooks, PR, IA).

## Flux Git

1. **Synchroniser** `main` (ou la branche de base du projet) avant de créer une branche.
2. **Créer une branche** dédiée, par ex. `feature/…`, `fix/…`, `chore/…`.
3. **Commits** atomiques et messages clairs (voir ci-dessous).
4. **Pousser** et ouvrir une **Pull Request** vers la branche cible ; remplir le template (tests, RLS, captures UI si front).
5. **Revue de code** : processus humain + IA (voir ci-dessous) ; intégrer les retours ; une PR = un sujet cohérent.

Des commandes pas à pas (branches, `git add`, push) sont aussi décrites dans **[git/README.md](git/README.md)**.

### Revue de code : humain + IA

1. **Auteur** : template PR rempli et **tests locaux** exécutés (checklist du template).
2. **IA (Claude en local ou CI)** : lancer l’**[Agent Review (code)](.github/prompts/agents/code-review.md)** sur le diff ou la PR ; publier le rapport en **brouillon** dans la **description du PR** ou dans un fichier **`review-notes.md`** sur la branche (selon les habitudes d’équipe — à retirer du diff avant merge si ce fichier ne doit pas être versionné).
3. **Humain** : **valider ou rejeter** chaque point (IA ou relecteurs) ; rien ne part en production sur la seule base d’une suggestion automatique.
4. **Approbations** : **au moins une approbation humaine** obligatoire pour merger ; pour la prod, l’équipe peut imposer **deux** approbations.
5. **Règle d’or** : **l’IA ne merge jamais seule** — elle **suggère** ; seuls les humains approuvent et fusionnent.

## Conventions de commit (Conventional Commits)

Format : `<type>(<scope>): <description courte>`

- **Types** courants : `feat`, `fix`, `chore`, `docs`, et aussi `refactor`, `perf`, `test`, `build`, `ci`, `revert` (voir `commitlint.config.cjs` à la racine).
- **Scopes** autorisés : `payroll`, `auth`, `frontend`, `infra`, plus `api` (API backend), `ci` (pipelines / outillage CI).
- Le **scope est optionnel** ; s’il est présent, il doit être dans la liste ci-dessus (ex. `docs:` sans scope reste valide).
- **Style** : impératif, souvent en français ; corps du message après une ligne vide si le contexte est utile.

Exemples :

```text
feat(frontend): ajuster le calendrier des absences
fix(api): normaliser les erreurs 422 sur la paie
fix(payroll): corriger le calcul des jours ouvrés
chore(ci): cache npm dans le workflow
docs: préciser les variables d’env Supabase dans le README backend
```

### Hooks (à la racine du dépôt)

1. **`npm install`** (racine) : installe **Husky** + **commitlint** ; le hook `commit-msg` vérifie le message avant enregistrement du commit ; le hook `pre-push` peut lancer les tests avant un push vers `main`. Guide lisible : **[.github/workflows/GUIDE_SIMPLE.md](.github/workflows/GUIDE_SIMPLE.md)**.
2. **pre-commit (Python)** : `pip install pre-commit` puis `pre-commit install` — exécute **Ruff** (lint + **ruff format**, équivalent pratique à **Black** pour le style) sur les fichiers `backend/**/*.py` modifiés. **mypy** n’est pas dans le hook par défaut ; ajout possible plus tard (hook `manual` ou config locale) quand les types et dépendances sont stabilisés.

## Fichiers de pilotage

- **[AGENTS.md](AGENTS.md)** : stack, commandes (`pytest`, `npm run lint`, `uvicorn`), interdits (secrets, SQL hors process), liens vers la doc technique et le déploiement.
- **`.cursor/rules/*.mdc`** : règles Cursor par zone (`backend/`, `frontend/`).

## Invoquer les agents (Cursor / IA)

- **Contexte automatique** : en ouvrant ou éditant des fichiers sous `backend/` ou `frontend/`, les règles `.cursor/rules/*.mdc` correspondantes s’appliquent selon les globs.
- **Contexte explicite** : joindre **`@AGENTS.md`** (ou `@backend/app/README.md`, `@DEPLOIEMENT.md`) dans le chat pour ancrer stack et commandes.
- **Tâches ciblées** : décrire le périmètre (fichiers, comportement attendu, « pas de refactor hors sujet ») — aligné avec les règles du dépôt et [AGENTS.md](AGENTS.md).

Les humains comme les agents doivent respecter : pas de secrets dans le dépôt, pas de migration SQL ad hoc sans processus d’équipe, tests et checklist PR quand c’est pertinent.
