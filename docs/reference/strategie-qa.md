# Stratégie QA EYWAI

Date : 2026-08-11 · Monté et passé en revue adversariale le même jour.

## Les trois étages

| Étage | Quoi | Quand | Où |
|---|---|---|---|
| 1. QA exploratoire IA | Claude + Playwright MCP explore l'app en utilisateur, relève bugs/console/réseau/UX | à la demande : `/qa-session` | env de **test** |
| 2. E2E Playwright | Suite de non-régression sur les parcours critiques | local (`npm run e2e`), après chaque déploiement du test, et chaque matin de semaine | env de **test** |
| 3. Smoke prod | GET anonymes : front servi, bundle JS chargeable, `/health` backend | toutes les heures, automatique | prod (lecture seule) |

Ce qui a été **écarté, et pourquoi** : Momentic / QA Wolf / BrowserStack
(3-4 abonnements prématurés pour un produit mono-dev) ; Meticulous
(enregistre les parcours de vrais utilisateurs → données de paie réelles
chez un tiers, exclu RGPD) ; Checkly (le smoke maison gratuit suffit à ce
stade — à reconsidérer si besoin de scénarios connectés multi-régions).

## Règles de sécurité (non négociables)

- **Jamais contre la prod** : garde en **allowlist** dans
  `frontend/e2e/helpers/env.ts` — seuls les hôtes de l'env de test,
  `localhost` et `127.0.0.1` sont acceptés pour `E2E_BASE_URL` et
  `E2E_API_URL`. Le seul contact avec la prod est le smoke anonyme en lecture.
- **Aucun artefact CI** : dépôt public ⇒ les artefacts GitHub Actions sont
  téléchargeables par n'importe qui. Le workflow E2E n'uploade donc RIEN
  (pas de rapport, ni screenshots, ni vidéos, ni traces — elles contiennent
  les réponses API avec données réelles et les jetons du compte QA). En CI,
  `PLAYWRIGHT_NO_MEDIA=1` coupe toute capture ; en cas d'échec, rejouer en
  local pour diagnostiquer.
- **Jamais le bouton « Resynchroniser depuis la prod »** (bandeau orange).
  Playwright rejette les `confirm()` par défaut, et aucune spec ne le vise.
- Aucun identifiant dans le dépôt : `.env.e2e` est gitignoré, la CI passe
  par les secrets GitHub. Les constats QA (nominatifs) vont dans
  `data/qa/constats/`, gitignoré — jamais dans `docs/`.
- Suite en `workers: 1` : l'env de test est partagé (Elsa peut y être).
- Les specs v1 sont en **lecture seule** (navigation, onglets, fiches). Les
  scénarios d'écriture (créer une absence, générer un bulletin) viendront en
  v2, avec nettoyage après test.

## Fichiers

- `frontend/e2e/helpers/env.ts` — URLs, allowlist anti-prod, lecture `.env.e2e`
- `frontend/e2e/helpers/erreurs.ts` — collecte console/5xx/réseau + `verifierPageSaine`
- `frontend/playwright.config.ts` — projets public/setup/connecte, médias coupés en CI
- `frontend/e2e/public/` — dispo + login (sans compte)
- `frontend/e2e/connecte/` — bandeau test, navigation 15 pages, collaborateurs, paie, exports
- `frontend/e2e/auth.setup.ts` — login unique, session réutilisée
- `scripts/qa/seed_qa_user.sql` — création du compte QA (mot de passe via `set_config('qa.pw', …)`)
- `.github/workflows/qa-e2e-test-env.yml` — E2E : après Deploy test env + cron + manuel
- `.github/workflows/qa-smoke-prod.yml` — smoke prod horaire
- `.claude/skills/qa-session/SKILL.md` — protocole d'exploration (`/qa-session`)
- `data/qa/constats/` — rapports des sessions exploratoires (gitignoré)

## Compte QA

`qa.playwright@eywai.access.local`, rôle `super_admin` (même modèle que le
compte plateforme existant : aucune ligne `user_company_accesses` requise),
uniquement sur l'env de test. Mot de passe **alphanumérique** (il transite
par un `-c` shell dans la resynchro) : `frontend/.env.e2e` en local, secrets
GitHub `QA_E2E_EMAIL` / `QA_E2E_PASSWORD` en CI.

La resynchro test←prod efface ce compte, et le workflow
`refresh-test-from-prod.yml` **le recrée automatiquement** (dernière étape,
via `psql` + `scripts/qa/seed_qa_user.sql`). Création manuelle : SQL Editor
du projet de test, `select set_config('qa.pw', '<mdp>', false);` suivi du
contenu du script dans la même exécution.

## Mise en service — faite le 2026-08-12

Compte QA créé sur l'env de test (auth.users + profiles + **super_admins** —
sans la ligne `super_admins`, le compte tombe dans l'Espace Collaborateur),
secrets GitHub `QA_E2E_EMAIL`/`QA_E2E_PASSWORD` posés, suite complète verte
(25 tests). Premiers constats applicatifs : `data/qa/constats/2026-08-12.md`.

## Lancer

```bash
cd frontend
npm run e2e            # toute la suite (env de test distant)
npm run e2e -- --project=public   # sans compte QA
npm run e2e:ui         # mode interactif
npm run e2e:report     # dernier rapport HTML (local uniquement)
npm run e2e:typecheck  # vérification TypeScript des specs
```

## Maintenance et évolutions prévues

1. **v2 écriture** : scénarios créer/annuler une absence, générer puis
   supprimer un bulletin sur un salarié dédié QA, avec nettoyage.
2. **Compte collaborateur** : dupliquer le seed avec rôle `salarie` pour
   tester l'espace collaborateur.
3. **`data-testid`** : en ajouter progressivement sur les éléments ciblés par
   les tests (le code n'en a aucun aujourd'hui — sélecteurs par rôle/texte).
4. Chaque bug corrigé (session `/qa-session` ou terrain) gagne sa spec de
   non-régression dans `frontend/e2e/`.

## Constats déjà relevés (2026-08-11)

- Le bandeau « ENVIRONNEMENT DE TEST » n'apparaît **pas sur la page de
  login** : rien n'y distingue le test de la prod, alors que le guide promet
  le bandeau « en haut de chaque page ». Suggestion : monter `TestEnvBanner`
  aussi sur les pages publiques (`/login`, `/forgot-password`).
