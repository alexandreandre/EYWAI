# Deux contrats le même mois (D3.1) — plan d'implémentation

> Exécution en ligne (superpowers:executing-plans), sans sous-agents (règle de consommation). Cases `- [ ]` à cocher.

**Objectif :** deux bulletins dans un mois où un contrat finit et un autre commence, un par contrat. Spécification : `docs/superpowers/specs/2026-10-31-deux-contrats-meme-mois-design.md`.

**Architecture :** une clé `contract_period_id` sur `payslips` et `monthly_inputs`. Elle est nulle pour le contrat de la fiche et remplie pour le contrat rangé du mois partagé. Toute lecture « du bulletin du mois » passe par un filtre unique (`du_contrat`), nul par défaut : rien ne change pour les données existantes. La génération reçoit la clé et la propage.

**Pile :** FastAPI et supabase-py (backend), React et TypeScript (frontend), PostgreSQL 17 (Supabase).

## Contraintes globales

- Aucune écriture dans la base de test ni de déploiement sans « déploie » d'Alexandre. La migration part avec le code.
- La DSN d'un mois partagé est refusée nommément. Sa forme est D3.2.
- Aucun nom de salarié dans les commits (hook `scripts/verifier_noms_salaries.py`).
- Tests : `backend/.venv/bin/python -m pytest -q tests/unit -p no:cacheprovider`. Deux échecs connus dus à l'environnement : `test_api_failure_manual_fallback` et `test_app_env_defaut_est_prod`.
- Frontend : `npm --prefix frontend run test -- --run`, puis `npm --prefix frontend run lint` et `tsc`.

---

### Tâche 1 : migration

**Fichiers :** créer `supabase/migrations/20261031120000_bulletin_par_contrat.sql`.

Contenu :
- `alter table payslips add column contract_period_id uuid references employee_contract_periods(id) on delete restrict` ; même chose sur `monthly_inputs` ;
- `drop index idx_payslips_company_unique` ; `create unique index idx_payslips_company_unique on payslips (company_id, employee_id, year, month, contract_period_id) nulls not distinct` ;
- un commentaire sur les deux colonnes ;
- la fonction `ranger_mois_partage(p_period uuid, p_employee uuid, p_year int, p_month int) returns jsonb`, `security definer`, `search_path = public`. Elle marque les bulletins et les variables à clé nulle du mois et rend `{"bulletins": n, "variables": m}`. Elle lève une exception si aucun bulletin n'est marqué. `grant execute` à `service_role` seulement, comme `prendre_verrou_generation_bulletin` (s'aligner sur sa migration).

Test : PostgreSQL 17 local jetable (`initdb` dans le scratchpad, socket `/tmp/pgs`). Créer des tables minimales, jouer la migration, puis vérifier :
- deux écritures à clé nulle donnent une ligne ;
- une écriture à clé remplie en donne une autre ;
- `ranger_mois_partage` marque 1 bulletin et 2 variables ;
- un second appel lève une exception (plus rien à clé nulle).

Commit : `feat(d3): clé du contrat sur les bulletins et les variables du mois`.

### Tâche 2 : le filtre de clé

**Fichiers :** créer `backend/app/shared/cle_du_bulletin.py` ; test `backend/tests/unit/shared/test_cle_du_bulletin.py`.

```python
CONFLIT_BULLETIN = "company_id,employee_id,year,month,contract_period_id"

def du_contrat(requete, contract_period_id: str | None):
    """Une lecture des bulletins ou des variables d'un mois, restreinte au bulletin d'un contrat.

    Clé nulle : le contrat de la fiche, c'est-à-dire tous les bulletins d'avant D3.
    Clé remplie : le contrat rangé d'un mois partagé.
    """
    if contract_period_id:
        return requete.eq("contract_period_id", str(contract_period_id))
    return requete.is_("contract_period_id", "null")
```

Tests sur `BaseEnMemoire` (`tests/unit/base_en_memoire.py`), avec deux lignes du même mois : la clé nulle rend l'une, la clé remplie rend l'autre.

### Tâche 3 : la fiche et le mois partagé

**Fichiers :** modifier `backend/app/modules/employees/application/contrat_du_mois.py` ; test `backend/tests/unit/employees/test_contrat_du_mois.py` (existe déjà : l'étendre).

- `LecteurContrats.contrat_range(period_id) -> dict | None` : lecture de la ligne de `employee_contract_periods` par id.
- `LecteurContrats.contrat_qui_finit_dans_le_mois(employee_id, year, month) -> dict | None` : ligne avec fiche dont `date_fin` tombe dans le mois.
- `fiche_du_mois(employee, year, month, contract_period_id=None)` : avec une clé, la fiche rangée de ce contrat (même transformation « parti » qu'aujourd'hui), quel que soit le mois. Sans fiche rangée, refus (`ValueError`) plutôt que la fiche d'un autre contrat.
- `mois_partage(employee, year, month) -> dict | None` : le contrat rangé qui finit dans le mois, si le contrat de la fiche commence dans ce même mois. Sinon None.

Tests :
- clé remplie au mois de début du contrat en cours → fiche rangée ;
- clé inconnue → refus ;
- `mois_partage` rend la période au mois commun, et None le mois suivant ou sans période qui finit dans le mois.

### Tâche 4 : « Nouveau contrat » le même mois

**Fichiers :** `backend/app/modules/employees/domain/nouveau_contrat.py`, `backend/app/modules/employees/application/nouveau_contrat.py`, l'aperçu du dialogue côté frontend (« Au plus tôt le … »). Tests dans `backend/tests/unit/employees/` (fichiers existants de nouveau contrat).

- `premier_jour_possible(precedent)` = le lendemain de la fin.
- `raison_du_refus` :
  - le refus « le mois où le précédent se termine » est retiré ;
  - le début doit être après la fin ;
  - le dernier bulletin généré reste exigé ;
  - nouveau paramètre `effets_par_mois: bool` : refus nommé si le bulletin de l'ancien contrat porte du CET ou de la modulation, et que le mois est partagé.
- `message_de_succes` : la phrase « Novembre 2026 aura deux bulletins… » quand le mois est partagé.
- `creer` : si le mois de début est celui de la fin, après `add_contract_period`, appeler `supabase.rpc("ranger_mois_partage", …)`. Si l'appel échoue, supprimer la ligne rangée et rendre la fiche, sur le même chemin que l'échec de rangement.
- Lecture des effets par mois : lignes du CET appliqué en paie et des crédits de modulation de (salarié, année, mois). Tables à lire dans `effets_du_bulletin.py` (`defaire_application_en_paie`, `defaire_credits_de_paie`).

Tests :
- domaine : début le même mois après la fin accepté ; début le jour de la fin refusé ; CET dans le mois partagé refusé ;
- application, sur `BaseEnMemoire` avec un `rpc` doublé : le marquage est appelé au mois partagé et pas sinon ; un marquage en échec remet la fiche et retire la ligne rangée.

### Tâche 5 : génération par contrat

**Fichiers :**
- `backend/app/modules/payslips/application/dto.py` : `contract_period_id: str | None = None` sur `GeneratePayslipInput` ;
- `backend/app/modules/payslips/application/commands.py` : `salarie_generable(..., contract_period_id)`, `_fetch_existing_payslip(..., contract_period_id)`, `archiver_version`, appel des effets ;
- `backend/app/modules/payslips/application/effets_du_bulletin.py` : `_bulletin_du_mois(..., contract_period_id)` ; avec une clé remplie, ne pas défaire le CET ni la modulation par mois ;
- `backend/app/modules/payslips/infrastructure/providers.py` : propagation à `process_payslip_generation` et au forfait ;
- `backend/app/modules/payroll/documents/payslip_generator.py` et `payslip_generator_forfait.py` : paramètre `contract_period_id`, avec :
  - `fiche_du_mois(..., contract_period_id)` ;
  - les variables lues par `du_contrat(...)` ;
  - pas de génération automatique des variables avec une clé ;
  - pas d'écriture dans `employee_schedules` avec une clé ;
  - écriture avec `"contract_period_id": contract_period_id` et `on_conflict=CONFLIT_BULLETIN` ;
- `backend/app/modules/payroll/documents/pdf_du_bulletin.py` : `chemin_enregistre(..., contract_period_id=None)` par `du_contrat` ; nom de PDF suffixé `_contrat-precedent` avec une clé ;
- la garde à clé nulle : si le bulletin en place a un `en_tete.salarie.date_entree` différent du début du contrat de la fiche et que le mois est partagé, `PayslipBadRequestError` avec le message de la spécification ;
- la route de génération (`backend/app/modules/payslips/api/`) accepte `contract_period_id`.

Tests, dans le style de `tests/unit/payslips/test_effets_du_bulletin.py` (base en mémoire) :
- `_fetch_existing_payslip` rend le bulletin de la clé demandée ;
- les effets refusés ou défaits ne visent que le bulletin de la clé ;
- `chemin_enregistre` par clé ;
- la garde refuse quand la date d'entrée diffère.

Pour le générateur, un test ciblé des branches extraites :
- `_variables_du_bulletin(employee_id, year, month, contract_period_id)` ;
- `_ecrit_le_planning(contract_period_id) -> bool`, extrait si l'écriture est trop enfouie.

### Tâche 6 : lectures « le bulletin du mois »

Chaque lecture par (salarié, année, mois) des sites suivants passe par `du_contrat(requete, contract_period_id)`. Le paramètre est nul par défaut, sauf pour les documents de sortie qui le reçoivent de l'appelant.
- `payslips/infrastructure/queries.py` : `get_payslip_data_du_mois` et `_cumuls_du_mois`, tous deux à clé nulle ;
- `payslips/application/suite_du_bulletin.py` (`_lire_bulletin_du_mois`, M+1, clé nulle). Un bulletin à clé remplie ne marque pas le mois suivant ;
- `payslips/application/coherence.py` ;
- `payslips/infrastructure/readers.py` ;
- `payroll/infrastructure/empreinte_entrees_queries.py` (`lire_bulletin_enregistre`) ;
- `payroll/engine/reference_remuneration.py` (deux lectures) ;
- `payroll/documents/salary_certificate_generator.py` ;
- `payroll/documents/payslip_run_heures.py` (lecture par mois de référence) ;
- `payroll/solde_de_tout_compte/common/bulletin_de_sortie.py` et `socle_commun.py`. Clé : `mois_partage(...)` du mois de sortie, si la sortie est celle du contrat rangé ;
- `participation/application/regularisation_bulletin_service.py` : lecture à clé nulle et `on_conflict=CONFLIT_BULLETIN` ;
- `payslips/infrastructure/repository.py` : suppression d'un bulletin. Les cumuls du mois ne sont vidés que pour une clé nulle ;
- `ijss_tracking/application/service.py` (`_bulletins_du_mois`) et `repos_compensateur/infrastructure/providers.py` : filtre à clé nulle.

Test : un test par module touché qui a déjà des tests. Il pose deux bulletins dans le mois et vérifie que la lecture rend celui à clé nulle.

### Tâche 7 : variables automatiques bornées au contrat

**Fichier :** `backend/app/modules/payroll_variables/application/generate_monthly.py`.
- Les règles qui comptent les postes du planning ne comptent que les jours entre le début du contrat de la fiche et sa sortie.
- Les écritures et suppressions ne visent que les variables à clé nulle.

Test : un panier du 5/11 n'est pas compté pour une entrée le 17/11 ; une variable à clé remplie survit à la régénération des variables.

### Tâche 8 : exports du mois

- Paiement des salaires (`exports/infrastructure/export_paiement_salaires.py` et `payroll/exports/paiement_salaires.py`) : la garde « Doublon détecté » porte sur l'id du bulletin.
- PDF du mois (`payslips/application/pdf_du_mois.py`) : un fichier par bulletin, plus un par salarié.
- Écritures comptables (`export_ecritures_comptables.py`) : les variables se rattachent au bulletin de leur clé.
- Provision de congés (`export_provision_cp.py`) : somme par (salarié, mois).
- Effectifs : salariés distincts dans le journal, les écritures comptables et `payroll_kpi_resolver.py`.
- DSN (`exports/infrastructure/export_dsn.py`, `payroll/exports/dsn.py`) : un bulletin à clé remplie dans le mois ajoute un manque bloquant, avec le message de la spécification. Il passe par le même chemin que les manques de fiche.

Tests : paiement à deux nets ; variables d'écritures comptées une fois ; effectif à 1 pour deux bulletins ; DSN refusée avec le message.

### Tâche 9 : écrans

- Backend : les listes de bulletins (liste de paie, fiche) rendent `contract_period_id`. La liste de paie rend, par salarié, `mois_partage` (dates du contrat rangé et id).
- `frontend/src/pages/rh/Payroll.tsx` et `features/payroll/utils/listeControleMois.ts`, `bulletinARecalculer.ts`, `validationMoisPrecedent.ts` : `.find(...)` sur le mois devient « le bulletin à clé nulle ». La ligne « Contrat précédent, jusqu'au … » porte le bulletin rangé et ses actions, qui appellent la génération avec `contract_period_id`. Le mois est complet quand les deux bulletins sont validés.
- « Corriger le bulletin » : la correction écrit la clé du bulletin corrigé sur ses variables (`payslips/application/corrections.py`).
- Saisie des variables : `monthly_inputs/infrastructure/repository.py` (`list_by_employee_period`) ne rend que la clé nulle.
- Le dialogue « Nouveau contrat » : « Au plus tôt le … » suit le nouveau premier jour possible. Le message de succès du serveur s'affiche tel quel.

Tests : Vitest des fonctions de `listeControleMois` et `bulletinARecalculer` avec deux bulletins dans le mois ; test backend de la correction avec une clé.

### Tâche 10 : vérification d'ensemble

- Suite unitaire backend complète, et frontend (tests, lint, types).
- Relecture du diff contre la spécification.
- Commit et poussée de la branche. Pas de déploiement : la migration attend « déploie ». Après déploiement : cas complet chez MAJI sur un salarié de Recette, supprimé ensuite, puis la vidéo H.5 réécrite.
