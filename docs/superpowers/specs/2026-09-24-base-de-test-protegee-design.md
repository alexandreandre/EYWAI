# La base de test est protégée comme une production

Décidé le 24/09/2026 avec Alexandre : « ma base de test est très importante
pour l'instant, et pourra même devenir la prod plus tard ».

## Pourquoi

Colorplast fait sa vraie paie sur l'environnement de test (« demo test paie ») :
bulletins janvier–juillet importés de Quadra, reprise au 31/07, paie d'août en
cours. Or trois chemins pouvaient effacer cette base, pensée à l'origine comme
jetable :

- le workflow « Refresh test from prod » remplace toute la base de test par la
  production, lançable en un clic depuis GitHub, sans confirmation (il a servi
  en août) ;
- `POST /api/test-env/refresh` déclenche ce workflow **sans authentification**
  (route inscrite dans la liste blanche des routes publiques). Inerte
  aujourd'hui faute de `GITHUB_DISPATCH_TOKEN` sur le service de test (vérifié
  par le nom des variables Cloud Run), mais à un réglage de l'effacement par
  n'importe qui ;
- le script `scripts/test_env/refresh_from_prod.sh`, lançable à la main.

## Ce qui change

1. **Script** : après les gardes de destination et avant la sortie `--dry-run`,
   il interroge la base cible ; si une société a une ligne dans
   `company_payroll_takeover` (reprise de paie), il refuse et nomme les
   sociétés. Si la base ne répond pas, il refuse aussi. Levée explicite :
   `REFRESH_ECRASER_PAIE_REELLE=oui`.
2. **Workflow** : champ `confirmation` obligatoire ; première étape qui refuse
   si la saisie n'est pas `EFFACER LA BASE DE TEST` (saisie passée par variable
   d'environnement, jamais interpolée). Même exigence via
   `client_payload.confirmation` pour `repository_dispatch`. Le re-seed du
   compte QA ne tourne plus si la confirmation est refusée.
3. **Route** : `Depends(verify_super_admin)` ; retirée de
   `ROUTES_PUBLIQUES_ASSUMEES`.
4. **Guide** `docs/guide-environnement-test.md` : resynchro verrouillée, bouton
   et bandeau décrits mais absents du frontend (retirés du texte), commande
   avec confirmation, sauvegardes.

## Sauvegardes (constat, rien à faire dans ce chantier)

`supabase backups list` : sauvegarde physique quotidienne, 7 jours de
rétention, PITR désactivé — une restauration peut perdre jusqu'à une journée de
saisie. Activer le PITR est une décision de coût, à prendre par Alexandre.

## Hors périmètre, à trancher

- Les tests d'intégration de la CI (PR et `main`) écrivent dans cette même
  base ; `qa-e2e-test-env.yml` y joue les tests E2E chaque matin et après
  chaque déploiement du test.
- `script-env-test.yml` et `recalage-cp-test.yml` y écrivent par conception
  (option `apply`).

## Tests

- `tests/unit/core/test_refresh_guard.py` : faux `psql` en tête de PATH —
  refus si la base porte une reprise (nommée), refus si la vérification échoue,
  levée explicite acceptée, cible sans paie réelle acceptée.
- `tests/unit/test_env/test_refresh_endpoint.py` : sans authentification →
  401/403 et rien n'est déclenché ; les autres cas avec un super admin simulé.
- `tests/unit/security/test_routes_authentifiees.py` : la route n'est plus dans
  la liste blanche.
