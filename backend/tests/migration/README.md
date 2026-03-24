# Tests de migration payroll (moteur dans `app` + runtime sous `app/runtime/payroll`)

Ces tests vérifient que la génération de bulletins dans `app.modules.payroll` reste conforme à l’ancienne logique des scripts historiques (`generateur_fiche_paie*.py`, aujourd’hui non invoqués par l’API).

**Données sur disque** : les fixtures et l’orchestration utilisent `app.core.paths` (`payroll_engine_root()`, etc.). La racine runtime est **`app/runtime/payroll/`** (`data/`, `templates/`), et non plus `backend_calculs/`.

## Contenu

- **PAYROLL_TRANSFER_AUDIT.md** : audit statique du transfert (mapping ancien flux → app).
- **test_payroll_transfer_audit.py** : vérifications de structure (mêmes fonctions, mêmes appels moteur).
- **fixtures.py** : construction de répertoires de test (contrat, entreprise, saisies, cumuls, calendriers, horaires, événements).
- **test_payroll_bulletin_compare_heures.py** : bulletin **heures** (montants cohérents, champs attendus).
- **test_payroll_bulletin_compare_forfait.py** : bulletin **forfait jour** (idem).

## Exécution

- Audit uniquement (pas de Supabase) :
  ```bash
  pytest tests/migration/test_payroll_transfer_audit.py -v
  ```

- Comparaison bulletins (nécessite Supabase : `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`) :
  ```bash
  pytest tests/migration/test_payroll_bulletin_compare_heures.py tests/migration/test_payroll_bulletin_compare_forfait.py -v
  ```
  Sans variables d’environnement, les tests de comparaison sont ignorés (`pytest.mark.skip`).

## Stratégie de comparaison

1. Créer les fichiers employé via `build_employee_fixture_dir(engine_root, …)` (écrit sous `payroll_engine_employee_folder(<nom>)` / `data/entreprise.json` relatifs à `payroll_engine_root()`).
2. Lancer la génération **app** (`run_payslip_generation_heures` / `run_payslip_generation_forfait`).
3. Vérifier structure du dict bulletin et ordres de grandeur des montants (brut, net, etc.).
