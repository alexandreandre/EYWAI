---
name: resync-test
description: >-
  Chiffre ce qui sera perdu et gagné, puis recommande avant de recopier la
  production vers l’environnement de test (workflow refresh-test-from-prod.yml).
  Diagnostic ordonné : date de dernière resynchro, travail sandbox perdu,
  périmité face à la prod (lecture seule), dérive de schéma, run en cours.
  À utiliser lorsque l’utilisateur demande /resync-test, de remettre le test
  à jour, ou de recopier la prod dans le test.
---

# Resync-test — chiffrer, recommander, puis recopier prod → test

## Objectif

**Ce n’est PAS un simple lanceur de workflow.** Avant toute action, **chiffrer**
ce qui sera perdu et ce qui sera gagné, produire une **recommandation
argumentée**, et n’exécuter la resynchro qu’après **accord explicite**.

## Quand utiliser ce skill

- L’utilisateur demande **`/resync-test`**, de **remettre le test à jour**,
  de **recopier la prod dans le test**, ou attache ce fichier.

## Contexte dépôt (ne pas réinventer)

| Élément | Fait |
|---------|------|
| Workflow | `.github/workflows/refresh-test-from-prod.yml` |
| Déclencheurs | `workflow_dispatch` et `repository_dispatch` (type `refresh-test-env`, bouton UI test) |
| Lancement | `gh workflow run refresh-test-from-prod.yml` |
| Sens | **UNIQUE** : lit la prod, écrit le test. Jamais l’inverse. |
| Sécurité prod | Connexion prod via un rôle PostgreSQL **EN LECTURE SEULE** : la prod **ne PEUT PAS** être modifiée. C’est **structurel**, pas une convention — le dire ainsi (c’est la question qui inquiète toujours). |
| Concurrence | `concurrency: group refresh-test-env, cancel-in-progress: false` — une seule resynchro à la fois |
| Effet | `DROP SCHEMA public CASCADE` puis restauration du dump prod → **TOUT** le bac à sable disparaît |
| Pivot diagnostic | Table `public.test_env_refresh_log (id, finished_at, employees_count)` — recréée par `scripts/test_env/neutralize_test_db.sql` à chaque copie ; **date** la dernière resynchro |
| API status | Backend test : `GET /api/test-env/status` (dernière resynchro sans identifiants de base) |
| Accès prod local | `backend/.env` via `app.core.database.get_supabase_client`. **Clés inversées** : `SUPABASE_KEY` = `service_role`, `SUPABASE_SERVICE_KEY` = `anon`. **Toutes** les requêtes prod en **LECTURE SEULE**. |
| Interdits | Ne jamais déclencher `deploy.yml` ni `deploy-test-env.yml` depuis cette commande |

---

## Garde-fous (obligatoires)

1. **Prod en lecture seule** uniquement — aucun `INSERT` / `UPDATE` / `DELETE` / DDL sur la production.
2. **Ne pas inventer** de chiffres si les mesures sont impossibles (identifiants test absents, API injoignable) — dégradation honnête (étape 6).
3. **Ne pas lancer** sans accord explicite ; si recommandation « Coûteuse », confirmation **renforcée**.
4. **Ne pas empiler** une seconde resynchro si un run est déjà actif.
5. En échec : `gh run view <id> --log-failed` — **ne pas** relancer d’office (état partiel possible).
6. **Ne jamais** déclencher `deploy.yml` ni `deploy-test-env.yml`.

---

## Workflow (à exécuter dans l’ordre)

```
Diagnostic resync-test :
- [ ] 1. Dater la dernière resynchro
- [ ] 2. Ce que l’on perd (sandbox test)
- [ ] 3. Ce que l’on gagne (prod depuis finished_at)
- [ ] 4. Dérive de schéma
- [ ] 5. Resynchro déjà en cours ?
- [ ] 6. Dégradation honnête (mesures manquantes)
- [ ] Recommandation + accord
- [ ] Lancement + suivi (seulement après accord)
- [ ] Synthèse finale
```

### 1. Dater la dernière resynchro

Priorité :

1. `GET /api/test-env/status` sur le **backend de test** (service `sirh-backend-test`).
   Résoudre l’URL si besoin (`gcloud run services describe sirh-backend-test …` ou URL connue du projet). Réponse typique : `is_test`, `last_refresh_at`.
2. Sinon, si accès SQL/API test disponible :
   `SELECT max(finished_at), employees_count FROM test_env_refresh_log` (ou équivalent via client test).

Afficher l’ancienneté en clair (« il y a 3 jours », « il y a 4 heures », « jamais »).

Noter `finished_at` → pivot pour les étapes 2 et 3. Si inconnu → l’indiquer et limiter le chiffrage.

### 2. CE QUE L’ON PERD — le chiffre qui manque aujourd’hui

Côté **TEST**, compter les lignes créées ou modifiées **APRÈS** `finished_at` sur les tables métier, notamment :

- `employees`, `payslips`, `absences`, `contracts`, `user_company_accesses`, `documents`
- et toute table pertinente portant `created_at` / `updated_at`

Critère typique : `created_at > finished_at OR updated_at > finished_at` (adapter aux colonnes réellement présentes).

Restituer en **langage métier**, pas en jargon SQL, par ex. :

> 43 bulletins générés, 2 sorties saisies, 7 fiches modifiées depuis la dernière copie — tout cela sera perdu.

Si le total est **nul** : le dire — **la resynchro ne coûte rien**.

### 3. CE QUE L’ON GAGNE — à quel point le test est périmé

Côté **PRODUCTION** (**lecture seule** uniquement) :

- Passer par `app.core.database.get_supabase_client` (depuis `backend/`, avec `.env`).
- Rappeler si besoin : les clés sont **inversées** dans `.env` — ne pas « corriger » en écrivant avec la mauvaise clé ; rester en lecture.
- Compter les lignes créées ou modifiées depuis le **même** `finished_at` (mêmes familles de tables).

Restituer de même :

> la prod a 128 éléments que le test ignore.

Si c’est **nul** : la resynchro **n’apporte rien**.

**Interdit** : toute écriture, migration, ou modification de données/prod.

### 4. DÉRIVE DE SCHÉMA

Comparer la **liste des tables** entre prod et test (ex. `information_schema.tables` schéma `public`, ou inventaire API équivalent).

- Un écart → le test tourne sur un **schéma périmé** : argument **fort** en faveur de la resynchro — le signaler explicitement (tables présentes d’un côté seulement).

### 5. Une resynchro déjà en cours ?

```bash
gh run list --workflow=refresh-test-from-prod.yml --limit 3
```

- Si un run a un statut actif (`queued`, `in_progress`, `waiting`, `pending`, `requested`) → **ne pas en lancer une seconde** ; proposer de suivre celle qui tourne (`gh run watch <id>`).

### 6. DÉGRADATION HONNÊTE

Si les identifiants du test ne sont pas disponibles localement (ou l’API status / le SQL test est injoignable) :

- **NE PAS INVENTER** de chiffres.
- Dire précisément quelles mesures n’ont pas pu être faites (ex. « perte sandbox non chiffrée — pas d’accès test » ; « dérive de schéma non vérifiée »).
- Laisser l’utilisateur décider **en connaissance de cause**.

Même règle si seul le status HTTP est OK mais les comptages table par table échouent.

---

## Recommandation argumentée (obligatoire avant action)

Choisir **l’une des trois** :

| Verdict | Quand |
|---------|--------|
| **Recommandée** | Rien (ou presque) à perdre côté test, test nettement périmé face à la prod (et/ou dérive de schéma). |
| **Inutile pour l’instant** | Copie récente, prod peu bougée : on ferait perdre du temps sans rien gagner. |
| **Coûteuse** | Travail en cours détecté dans le bac à sable : **énumérer** ce qui disparaîtra et demander une **confirmation renforcée**. |

Présenter brièvement les chiffres (perdu / gagné / schéma / ancienneté), le verdict, puis **demander l’accord**. Ne lancer qu’après accord explicite.

---

## Après accord uniquement

### Prévenir

L’opération est **LONGUE** (souvent plusieurs minutes, timeout workflow jusqu’à 60 min). Le dire clairement pour ne pas laisser croire à un blocage.

### Déclencher et suivre

```bash
gh workflow run refresh-test-from-prod.yml
gh run list --workflow=refresh-test-from-prod.yml --limit 3
gh run watch <id>
```

### En cas d’échec

```bash
gh run view <id> --log-failed
```

- Montrer les logs pertinents.
- **NE PAS** relancer d’office — une copie interrompue peut laisser le test dans un **état partiel**.

### Interdits post-accord (inchangés)

- Pas de `deploy.yml` (production).
- Pas de `deploy-test-env.yml` (déploiement de code) — la resynchro ne change que les **données**.

---

## Synthèse finale (en français)

Après succès (ou à la clôture du suivi), indiquer :

1. **Date** de la resynchro (nouvelle `finished_at` / status).
2. **Durée** du run.
3. **Nombre de salariés copiés** (`employees_count` dans `test_env_refresh_log` si disponible).
4. **Rappel** : le **CODE** déployé sur le test **n’a pas changé** — seules les **données** ont bougé.

---

## Anti-patterns à éviter

- Lancer le workflow sans chiffrage ni recommandation.
- Inventer des volumes « perdus / gagnés ».
- Écrire quoi que ce soit en production.
- Empiler une seconde resynchro concurrente.
- Relancer automatiquement après un échec.
- Déclencher un déploiement (`deploy.yml` / `deploy-test-env.yml`) « tant qu’on y est ».
- Laisser croire que la resynchro met à jour le code Cloud Run.

---

## Exemple d’invocation

> `/resync-test` — je veux remettre le test à jour depuis la prod.

L’agent date la dernière copie, chiffre pertes et gains, signale toute dérive de schéma, recommande (Recommandée / Inutile / Coûteuse), attend l’accord, puis lance et suit `refresh-test-from-prod.yml`.
