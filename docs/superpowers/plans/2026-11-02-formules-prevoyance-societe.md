# Formules de prévoyance par société : plan d'implémentation

> **Pour l'exécution :** en ligne, tâche par tâche, en TDD (règle de consommation : pas de sous-agents). Cases `- [ ]` à cocher.

**But :** la RH crée des formules de prévoyance par société, puis les choisit sur la fiche. Les lignes de la formule sont copiées sur la fiche.

**Architecture :**
- une table `company_prevoyance_formules` ;
- un module backend `prevoyance_formules`, sur le modèle de `mutuelle_types` ;
- `specificites_paie.prevoyance.formule_id` sur la fiche, retiré de l'empreinte.

Le moteur n'est pas touché.

**Pile :** FastAPI et Supabase (Python 3.11), React avec react-hook-form, zod et react-query (Vitest).

## Contraintes globales
- **Calcul** : aucune ligne du moteur de paie ne change, et l'empreinte d'une fiche sans `formule_id` reste identique au hash figé (`test_empreinte_donnees_dsn.py`).
- **Textes d'écran** : en français, le produit s'appelle « Martine », et pas de « (s) » (`tests/unit/architecture/test_pas_de_pluriel_entre_parentheses.py`).
- **Routeurs** : pas d'accès direct à la base (`test_router_db_guard.py`).
- **Bases d'une ligne** : `brut_plafonne` par défaut, `tranche_2` ou `brut`. Les taux sont en fraction. Une ligne garde toutes ses clés.
- **Dépôt public** : aucun nom de salarié dans le code ni dans les commits.

---

### Tâche 1 : `formule_id` hors de l'empreinte
**Fichiers :** modifier `backend/app/modules/payroll/application/empreinte_entrees_service.py` (`_fiche`). Test : créer `backend/tests/unit/payroll/test_empreinte_formule_prevoyance.py`.
**Produit :** `_fiche(employee)` retire `specificites_paie.prevoyance.formule_id`, et ne recopie `prevoyance` que si la clé est présente.
- [ ] Tests, sur la fiche et les constantes de `test_empreinte_donnees_dsn.py` (EMPLOYEE, `_globale`, `_partie_fiche`) :
  - `test_le_lien_a_une_formule_ne_change_pas_l_empreinte` : prévoyance `{adhesion: True, formule_id: "f1"}`, empreintes égales aux hash figés ;
  - `test_changer_de_formule_sans_changer_les_lignes_ne_change_rien` ;
  - `test_une_ligne_de_prevoyance_change_toujours_l_empreinte` ;
  - `test_la_fiche_lue_n_est_pas_modifiee`.
- [ ] Les voir échouer. Implémenter. Les voir passer, avec `test_empreinte_*.py`.
- [ ] Commit `fix(empreinte): le lien d'une fiche à sa formule de prévoyance ne périme aucun bulletin`.

### Tâche 2 : table et règle pure
**Fichiers :**
- créer `supabase/migrations/20261102120000_company_prevoyance_formules.sql` : table, index `company_id`, RLS copiée de `company_mutuelle_types` (lecture pour les membres, écriture pour admin, rh et collaborateur_rh), contrôle `statut_categoriel in ('cadre','non_cadre','tous')`, `lignes jsonb not null default '[]'` ;
- créer `backend/app/modules/prevoyance_formules/__init__.py` et `domain/rules.py`.

**Produit (`domain/rules.py`) :**
- `appliquer_formule(prevoyance: Mapping | None, formule: Mapping) -> dict` : copie profonde des `lignes` dans `lignes_specifiques`, `formule_id = str(formule["id"])`, `adhesion` gardée (vraie si absente), autres clés gardées.
- `lignes_identiques(a, b) -> bool` : compare les lignes sans tenir compte de `id`, avec les taux en float et la base absente valant `brut_plafonne`.
- `fiche_a_mettre_a_jour(specificites, formule) -> bool` : `formule_id` égal et lignes différentes.
- `formule_convient(formule, cadre: bool) -> bool` : `tous`, ou bien la catégorie de la formule correspond.

**Tests (`backend/tests/unit/prevoyance_formules/test_rules.py`) :** copie et remplacement ; `adhesion` et clé inconnue gardées ; l'entrée n'est pas modifiée ; identité tolérante sur `id` et la base par défaut ; une ligne en plus rend la fiche à mettre à jour ; filtre de catégorie.
- [ ] Rouge, vert, commit `feat(prévoyance): formules de société, table et règle de copie`.

### Tâche 3 : dépôt, commandes, routes
**Fichiers :** créer dans `backend/app/modules/prevoyance_formules/` :
- `infrastructure/repository.py` : `lister(company_id)`, `lire(id, company_id)`, `creer(row)`, `modifier(id, company_id, patch)`, `fiches_de_la_societe(company_id)` (id, specificites_paie, updated_at), `ecrire_prevoyance(employee_id, specificites, updated_at) -> bool` (mise à jour conditionnée sur `updated_at`) ;
- `schemas.py` : `LignePrevoyance` (extra autorisé), `FormuleCreate` et `FormuleUpdate` ;
- `application/service.py` : `lister_formules`, `creer_formule`, `modifier_formule`, qui renvoie `{formule, fiches_a_mettre_a_jour}`, `retirer_formule` (`is_active` à false), `appliquer_formule_aux_fiches(id, company_id) -> int` ;
- `api/router.py` ;
- l'inscription dans `backend/app/api/router.py`.

**Tests (`backend/tests/unit/prevoyance_formules/test_service.py`, dépôt simulé) :**
- le compte des fiches à mettre à jour ;
- `appliquer` ne réécrit que les fiches qui divergent, et compte les écritures ;
- une formule d'une autre société donne 404 ;
- des lignes sans libellé donnent 422.

Les tests d'architecture passent.
- [ ] Rouge, vert, commit `feat(prévoyance): API des formules de société`.

### Tâche 4 : la fiche garde la base et le lien
**Fichiers :** modifier `frontend/src/features/employee-detail/components/employeeProfileEditSchema.ts` et `frontend/src/features/employees/components/createEmployeeFormSchema.ts` : ligne `.passthrough()` et `formule_id: z.string().nullable().optional()`. Modifier `employeeProfileFormUtils.ts` pour charger et écrire `formule_id`.
**Tests :**
- `employeeProfileFormUtils.test.ts` : une ligne `base: 'tranche_2'` survit à la validation et à l'enregistrement ; `formule_id` est relu et réécrit ;
- `createEmployeeFormSchema.test.ts` : la base est gardée.
- [ ] Rouge (le défaut est confirmé par une sonde le 02/11 : `base` disparaît), vert, commit `fix(fiche): une ligne de prévoyance garde sa base (tranche B) à l'enregistrement`.

### Tâche 5 : client API et aides
**Fichiers :** créer `frontend/src/api/prevoyanceFormules.ts` (types `FormulePrevoyance`, `LignePrevoyance`, fonctions CRUD et `appliquer`) et `frontend/src/features/employees/utils/formulesPrevoyance.ts` : `formulesPourLeStatut(formules, cadre)`, `lignesDeLaFormule(formule)` (copie, `id` `prevoyance_<n>`), `lignesModifiees(lignes, formule)`.
**Tests :** `formulesPrevoyance.test.ts`.
- [ ] Rouge, vert, commit.

### Tâche 6 : la liste « Formule de la société » sur la fiche
**Fichiers :** modifier `frontend/src/features/employees/components/PrevoyanceAffiliationFields.tsx`.
- Une liste sous la case d'adhésion, alimentée par react-query `['prevoyance-formules']`, filtrée par statut.
- Le choix appelle `setValue` sur les lignes et le `formule_id`.
- L'option « Aucune (lignes saisies à la main) » efface `formule_id`.
- La mention « Lignes modifiées depuis la formule » s'affiche si `lignesModifiees`.
- « Formule retirée » s'affiche si la formule est inactive.
- Le composant ne s'affiche que s'il existe au moins une formule.

**Test :** `PrevoyanceAffiliationFields.test.tsx` (choix d'une formule → lignes copiées).
- [ ] Rouge, vert, commit.

### Tâche 7 : section société « Formules de prévoyance »
**Fichiers :** créer `frontend/src/features/company/components/CompanyPrevoyanceFormulesSection.tsx`, à insérer dans `CompanyPayrollTab.tsx` sous la mutuelle.
- Liste, avec le libellé, la catégorie et le nombre de lignes.
- Fenêtre de création et de modification : libellé, catégorie, lignes (libellé, taux salarial %, taux patronal %, forfait social %, base Tranche A, Tranche B ou Brut).
- Retirer.
- Après une modification, si `fiches_a_mettre_a_jour > 0`, un bandeau « N fiches ont encore les anciennes lignes » avec le bouton « Mettre à jour ces fiches ». Il appelle `appliquer` puis confirme « N fiches mises à jour : leurs brouillons sont à recalculer ».

**Test :** les aides de pluriel et de message, dans un fichier `.ts` testé.
- [ ] Rouge, vert, commit.

### Tâche 8 : remplir le catalogue depuis les fiches
**Fichiers :** créer `backend/scripts/creer_formules_prevoyance.py`, sur le modèle de `poser_subrogation_jamais.py` : simulation avec piège et empreinte, `--ecrire --empreinte`, sauvegarde.
- Un jeu distinct de lignes (`lignes_identiques`) par société et par catégorie (cadre ou non-cadre).
- Libellé : « Prévoyance cadre » ou « Prévoyance non-cadre », suffixé A, B… s'il y en a plusieurs, et suivi du nombre de fiches.
- Les fiches de lignes identiques sont reliées par `formule_id` ; les lignes ne changent pas.
- [ ] Simulation lancée, résultat noté. L'écriture attend « lance creer_formules_prevoyance ».

### Tâche 9 : vérifier, pousser, déployer
- [ ] Suites backend et frontend complètes, puis lint (ruff, eslint), types (tsc) et build.
- [ ] Pousser, CI verte, puis `gh workflow run deploy-test-env.yml --ref feat/dsn-octobre -f migration=20261102120000_company_prevoyance_formules.sql`. Contrôler le run et /health.
- [ ] Jouer le parcours sur le site de test chez MAJI : créer une formule, la choisir sur une fiche de démonstration, enregistrer, contrôler que la base est gardée, puis tout remettre en place.
