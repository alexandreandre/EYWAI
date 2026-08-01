---
name: deploy-test
description: >-
  Diagnostique puis déploie une branche sur l’environnement de test Cloud Run
  (workflow deploy-test-env.yml), jamais la production. Produit un diagnostic
  ordonné (branche, arbre sale, commits non poussés, commit actuellement sur
  le test, delta réel, alerte migrations schéma, pré-vol CI unit, run en
  cours) avant de demander le feu vert. À utiliser lorsque l’utilisateur
  demande /deploy-test, de déployer sur le test, ou d’essayer sa branche sur
  l’environnement de test.
---

# Deploy-test — diagnostic puis déploiement sur l’env de test

## Objectif

**Ce n’est PAS un simple lanceur de workflow.** Avant toute action, établir un
**diagnostic** complet, le présenter à l’utilisateur pour **décision**, et
n’exécuter le déploiement qu’après **feu vert explicite**.

## Quand utiliser ce skill

- L’utilisateur demande **`/deploy-test`**, de **déployer sur le test**,
  d’**essayer sa branche sur l’environnement de test**, ou attache ce fichier.

## Contexte dépôt (ne pas réinventer)

| Élément | Fait |
|---------|------|
| Workflow test | `.github/workflows/deploy-test-env.yml` — `workflow_dispatch` seul |
| Lancement | `gh workflow run deploy-test-env.yml --ref <branche>` |
| Services | `sirh-backend-test`, `sirh-frontend-test` |
| Front test | https://sirh-frontend-test-505040845625.europe-west1.run.app (bandeau orange) |
| Migrations | **Le workflow n’applique AUCUNE migration.** Le test partage le schéma issu de la dernière resynchro depuis la production. |
| Production | `.github/workflows/deploy.yml` — **JAMAIS** le déclencher ni le proposer |
| Commit / push | Skill **`/push`** (`.cursor/skills/push/SKILL.md`) — **ne pas** redupliquer ; y renvoyer |
| CI bloquante | `python -c "from app.main import app; app.openapi()"` puis `python -m pytest tests/unit` (Ruff = `continue-on-error`, non bloquant) |

---

## Garde-fous (obligatoires)

1. **Refuser** `main` / `master` — la prod a son propre circuit.
2. **Ne jamais** `git add -A` ni committer d’office (sessions parallèles possibles).
3. **Ne jamais** déclencher ni proposer `deploy.yml` (production).
4. **Ne jamais** lancer `pytest` en entier pour décider — uniquement `tests/unit`.
5. **Ne pas déployer** sans feu vert explicite de l’utilisateur.
6. **Ne pas empiler** un second déploiement si un run test est déjà en cours.
7. En cas d’échec du run : logs via `gh run view <id> --log-failed` — **ne pas** relancer d’office.

---

## Workflow (à exécuter dans l’ordre)

Copier et suivre cette checklist :

```
Diagnostic deploy-test :
- [ ] 1. Branche courante
- [ ] 2. Arbre de travail (fichiers non commités)
- [ ] 3. Commits non poussés
- [ ] 4. Commit actuellement sur le test
- [ ] 5. Delta réel (commits + domaines)
- [ ] 6. Alerte migrations
- [ ] 7. Pré-vol local (openapi + unit)
- [ ] 8. Run déjà en cours ?
- [ ] Synthèse de décision + feu vert
- [ ] Déploiement + suivi (seulement après accord)
```

### 1. Branche courante

```bash
git branch --show-current
```

- Si **`main`** ou **`master`** → **arrêter**. Expliquer que la prod a son propre circuit ; cette commande ne déploie que sur le test depuis une branche non-prod.
- Sinon, noter la branche `<branche>` pour le reste du diagnostic et le futur `--ref`.

### 2. Arbre de travail

```bash
git status -sb
git status --porcelain
```

- **NE JAMAIS** faire `git add -A` ni committer d’office : plusieurs sessions peuvent travailler en parallèle sur le même arbre ; stager aveuglément expédierait le travail en cours d’un autre.
- Lister les fichiers non commités.
- Dire clairement qu’ils **NE partiront PAS** dans le déploiement (le workflow lit la branche distante / le commit poussé).
- Si des changements locaux doivent être inclus → proposer **`/push`** (skill push), sans en exécuter la logique ici.

### 3. Commits non poussés

```bash
git fetch origin "<branche>" 2>/dev/null || true
git log "origin/<branche>..HEAD" --oneline
```

- Le déploiement lit la branche **DISTANTE** : sans push, il livrerait l’état précédent **sans aucune erreur**.
- Si des commits locaux ne sont pas sur `origin/<branche>` → les lister et indiquer qu’il faut **`/push`** avant un déploiement utile.

### 4. Quel commit tourne actuellement sur le test

```bash
gh run list --workflow=deploy-test-env.yml \
  --json headSha,conclusion,createdAt,headBranch \
  --limit 20
```

- Prendre le **dernier run réussi** (`conclusion == success`).
- Son **`headSha`** est le code en place → noter `<sha_déployé>`.
- Si aucun run réussi : le signaler ; le delta (étape 5–6) peut être partiel ou impossible — indiquer clairement la limite.

### 5. Delta réel

Si `<sha_déployé>` est connu :

```bash
git log <sha_déployé>..HEAD --oneline
git diff --stat <sha_déployé>..HEAD
```

Résumer en langage clair :

- combien de commits ;
- quels domaines touchés : **backend seul**, **frontend seul**, ou **les deux** (chemins `backend/`, `frontend/`, éventuellement autres) ;
- cela indique **quoi retester** ensuite.

### 6. Alerte migrations — contrôle le plus important

```bash
git diff --name-only <sha_déployé>..HEAD -- supabase/migrations/
```

Si la liste **n’est pas vide** → **AVERTIR FORTEMENT** :

- Le nouveau code tournera contre l’**ANCIEN schéma**.
- L’échec sera **silencieux et déroutant** (pas d’étape migration dans le workflow).
- Deux issues possibles :
  1. **`/resync-test`** — recopie le schéma de **production** ; n’aide que si la migration est **déjà en production**.
  2. **Appliquer la migration à la main** sur la base de test.
- Demander une **confirmation explicite** pour continuer malgré tout. Sans cette confirmation, **ne pas déployer**.

### 7. Pré-vol local — échouer en 60 s plutôt qu’en 5 min

Depuis `backend/`, jouer les **deux étapes bloquantes** de la CI :

```bash
.venv/bin/python -c "from app.main import app; app.openapi()"
.venv/bin/python -m pytest tests/unit -q
```

- Si l’une échoue → **ne pas déployer**, montrer l’échec.
- **Ne jamais** lancer `pytest` en entier pour décider : la suite d’intégration porte des échecs **pré-existants** sans rapport avec le code en cours. S’en tenir à `tests/unit` (ce que la CI bloque).
- Ruff n’est pas bloquant en CI → ne pas en faire un critère d’arrêt ici.

### 8. Un déploiement de test déjà en cours ?

```bash
gh run list --workflow=deploy-test-env.yml \
  --json databaseId,status,conclusion,headBranch,createdAt,url \
  --limit 5
```

- Si un run a `status` ∈ {`queued`, `in_progress`, `waiting`, `pending`, `requested`} → **ne pas en empiler un second**. Afficher l’URL / l’id du run en cours et attendre ou proposer de le suivre.

---

## Synthèse de décision (avant tout déploiement)

Présenter à l’utilisateur, en français :

1. **Ce qui va être déployé** : branche, commit distant (après push si pertinent), résumé du delta.
2. **Ce qui ne le sera pas** : fichiers locaux non commités / non poussés.
3. **Risques détectés** : migrations, pré-vol, run en cours, branche refusée, etc.
4. **Recommandation nette** : déployer / pousser d’abord / resync ou migration manuelle / corriger les tests / attendre le run en cours.

Puis : **demander le feu vert**. Ne pas déployer sans.

---

## Après feu vert uniquement

### Déclencher

```bash
gh workflow run deploy-test-env.yml --ref "<branche>"
```

### Suivre le run

```bash
# Récupérer l’id du run fraîchement créé (filtrer par branche)
gh run list --workflow=deploy-test-env.yml --branch "<branche>" --limit 3
gh run watch <id>
```

### En cas d’échec

```bash
gh run view <id> --log-failed
```

- Montrer les logs pertinents.
- **Ne pas** relancer d’office.

### En cas de succès

- URL du front test : https://sirh-frontend-test-505040845625.europe-west1.run.app
- Rappel : sur cet environnement, **e-mails**, **signature électronique** et **dépôt DSN** sont **neutralisés**.

---

## Anti-patterns à éviter

- Lancer le workflow sans diagnostic ni feu vert.
- Déployer depuis `main` / `master`.
- Proposer ou déclencher `deploy.yml` (production).
- `git add -A` / commit automatique « pour déployer ».
- Ignorer les commits non poussés (déploiement « réussi » de l’ancien code).
- Ignorer des fichiers sous `supabase/migrations/` dans le delta.
- Lancer toute la suite pytest (intégration) pour décider.
- Empiler un second `deploy-test-env` alors qu’un run est déjà actif.
- Relancer automatiquement après un échec.

---

## Exemple d’invocation

> `/deploy-test` — j’aimerais essayer ma branche sur l’environnement de test.

L’agent enchaîne les 8 points de diagnostic, présente la synthèse de décision, attend le feu vert, puis déclenche et suit `deploy-test-env.yml` uniquement.
