# Bac à sable sans synchronisation du salaire — plan d'exécution

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** un calcul en bac à sable n'écrit plus `employees.salaire_de_base`, et ses montants restent ceux d'une vraie génération.

**Architecture:** le calcul de la synchronisation est extrait dans une méthode du dépôt qui n'écrit rien (`salaire_de_base_a_date`) ; `sync_salaire_actif` l'appelle puis écrit ; `prepare_salary_evolution_for_payslip` reçoit `persister` et, en bac à sable, applique ce calcul à la fiche relue en mémoire. Les deux générateurs passent `persister=bac_a_sable is None`.

**Tech Stack:** Python 3.12, pytest, Supabase (PostgREST).

Spec : `docs/superpowers/specs/2026-09-24-bac-a-sable-sans-synchro-salaire-design.md`.

## Global Constraints

- Interpréteur `backend/.venv/bin/python` ; tests comme la CI, depuis `backend/` :
  `APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key .venv/bin/python -m pytest tests/unit`
- Une vraie génération (`persister=True`, valeur par défaut) ne change pas de comportement.
- Aucune écriture sur la base de test pendant la vérification : toutes les écritures PostgREST sont piégées.
- Ne jamais commiter `AGENTS.md`, `docs/audit-maji-2026/` ni `backend/app/runtime/payroll/data/employes/TEST_MIG_*`.

---

### Task 1 : le dépôt sait calculer la synchronisation sans l'écrire

**Files:**
- Modify: `backend/app/modules/employees/infrastructure/repository.py` (méthode `sync_salaire_actif`, ~l. 306-325)
- Test: `backend/tests/unit/employees/test_salaire_de_base_a_date.py` (nouveau)

**Interfaces:**
- Produces: `EmployeeRepository.salaire_de_base_a_date(employee_id: str, company_id: str, as_of: date) -> Optional[Dict[str, Any]]` — le `salaire_de_base` que la synchronisation écrirait, ou `None` si le salarié est introuvable. N'écrit jamais.
- `sync_salaire_actif(employee_id, company_id, as_of)` garde sa signature et son résultat.

- [ ] **Step 1 : écrire les tests qui échouent**

`backend/tests/unit/employees/test_salaire_de_base_a_date.py` :

```python
"""Le salaire que la synchronisation écrirait, calculé sans l'écrire.

Le bac à sable de génération doit voir la fiche telle qu'une vraie génération
la verrait après synchronisation, sans rien écrire (spec 2026-09-24).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.employees.infrastructure.repository import EmployeeRepository

pytestmark = pytest.mark.unit

EMPLOYEE_ID = "emp-sync"
COMPANY_ID = "co-sync"
AUJOURD_HUI = date(2026, 9, 24)
HISTORIQUE = [
    {
        "effective_date": "2026-05-01",
        "ancien_salaire": {"valeur": 2000.0},
        "nouveau_salaire": {"valeur": 2100.0},
    }
]


def test_rend_la_fiche_au_salaire_actif_sans_ecrire():
    repo = EmployeeRepository()
    fiche = {"id": EMPLOYEE_ID, "salaire_de_base": {"type": "mensuel", "valeur": 2000.0}}
    with (
        patch.object(repo, "get_by_id", return_value=fiche),
        patch.object(repo, "get_salary_history", return_value=HISTORIQUE),
        patch.object(repo, "update") as update,
    ):
        sb = repo.salaire_de_base_a_date(EMPLOYEE_ID, COMPANY_ID, AUJOURD_HUI)

    assert sb == {"type": "mensuel", "valeur": 2100.0}
    assert fiche["salaire_de_base"] == {"type": "mensuel", "valeur": 2000.0}
    update.assert_not_called()


def test_salarie_introuvable():
    repo = EmployeeRepository()
    with (
        patch.object(repo, "get_by_id", return_value=None),
        patch.object(repo, "update") as update,
    ):
        assert repo.salaire_de_base_a_date(EMPLOYEE_ID, COMPANY_ID, AUJOURD_HUI) is None
    update.assert_not_called()


def test_la_synchronisation_ecrit_exactement_ce_calcul():
    repo = EmployeeRepository()
    calcule = {"type": "mensuel", "valeur": 2100.0}
    with (
        patch.object(repo, "salaire_de_base_a_date", return_value=calcule) as calcul,
        patch.object(repo, "update", return_value={"id": EMPLOYEE_ID}) as update,
    ):
        resultat = repo.sync_salaire_actif(EMPLOYEE_ID, COMPANY_ID, AUJOURD_HUI)

    calcul.assert_called_once_with(EMPLOYEE_ID, COMPANY_ID, AUJOURD_HUI)
    update.assert_called_once_with(EMPLOYEE_ID, {"salaire_de_base": calcule})
    assert resultat == {"id": EMPLOYEE_ID}


def test_la_synchronisation_d_un_salarie_introuvable_n_ecrit_rien():
    repo = EmployeeRepository()
    with (
        patch.object(repo, "salaire_de_base_a_date", return_value=None),
        patch.object(repo, "update") as update,
    ):
        assert repo.sync_salaire_actif(EMPLOYEE_ID, COMPANY_ID, AUJOURD_HUI) is None
    update.assert_not_called()
```

- [ ] **Step 2 : vérifier l'échec**

Run: `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key .venv/bin/python -m pytest tests/unit/employees/test_salaire_de_base_a_date.py -q`
Expected: FAIL — `AttributeError: ... does not have the attribute 'salaire_de_base_a_date'` (ou `object has no attribute`).

- [ ] **Step 3 : extraire le calcul**

Dans `repository.py`, remplacer la méthode `sync_salaire_actif` par :

```python
    def salaire_de_base_a_date(
        self,
        employee_id: str,
        company_id: str,
        as_of: date,
    ) -> Optional[Dict[str, Any]]:
        """Le salaire_de_base que la synchronisation écrirait à as_of, sans l'écrire.

        Sert au bac à sable de génération, qui doit calculer sur la fiche
        synchronisée sans rien écrire (spec 2026-09-24).
        """
        emp = self.get_by_id(employee_id, company_id)
        if emp is None:
            return None
        timeline = self.get_salary_history(employee_id, company_id)
        fallback = _valeur_salaire_row(emp)
        valeur = salaire_actif_a_date(timeline, as_of, fallback)
        sb = emp.get("salaire_de_base")
        if isinstance(sb, dict):
            new_sb = dict(sb)
            new_sb["valeur"] = valeur
        else:
            new_sb = {"valeur": valeur}
        return new_sb

    def sync_salaire_actif(
        self,
        employee_id: str,
        company_id: str,
        as_of: date,
    ) -> Optional[Dict[str, Any]]:
        """Aligne employees.salaire_de_base sur le salaire actif à as_of (timeline)."""
        new_sb = self.salaire_de_base_a_date(employee_id, company_id, as_of)
        if new_sb is None:
            return None
        return self.update(employee_id, {"salaire_de_base": new_sb})
```

- [ ] **Step 4 : vérifier que tout passe, anciens tests compris**

Run: `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key .venv/bin/python -m pytest tests/unit/employees -q`
Expected: tout PASS (dont `test_commands_salary_deferred.py`, inchangé).

- [ ] **Step 5 : linter**

Run: `cd backend && .venv/bin/python -m ruff check app/modules/employees/infrastructure/repository.py tests/unit/employees/test_salaire_de_base_a_date.py`
Expected: aucune erreur nouvelle (comparer au même fichier avant modification si le fichier en portait déjà).

- [ ] **Step 6 : commit**

```bash
git add backend/app/modules/employees/infrastructure/repository.py backend/tests/unit/employees/test_salaire_de_base_a_date.py
git commit -m "refactor(paie): la synchronisation du salaire se calcule sans ecrire"
```

---

### Task 2 : la préparation du salaire n'écrit plus en bac à sable

**Files:**
- Modify: `backend/app/modules/payroll/application/salary_evolution_payroll.py` (`prepare_salary_evolution_for_payslip`, ~l. 88-131)
- Modify: `backend/app/modules/payroll/documents/payslip_generator.py` (~l. 1036)
- Modify: `backend/app/modules/payroll/documents/payslip_generator_forfait.py` (~l. 432)
- Test: `backend/tests/unit/payroll/test_salary_evolution_payroll.py` (ajouts en fin de fichier)

**Interfaces:**
- Consumes: `EmployeeRepository.salaire_de_base_a_date(employee_id, company_id, as_of) -> Optional[Dict[str, Any]]` (Task 1).
- Produces: `prepare_salary_evolution_for_payslip(employee_id: str, company_id: str, year: int, month: int, persister: bool = True) -> Dict[str, Any]`.

- [ ] **Step 1 : écrire les tests qui échouent**

Ajouter en fin de `backend/tests/unit/payroll/test_salary_evolution_payroll.py` :

```python
@patch("app.modules.payroll.application.salary_evolution_payroll._lire_bulletins_anterieurs", return_value=[])
@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_bac_a_sable_ne_synchronise_pas(mock_repo_cls, mock_sync, mock_lire):
    """Spec 2026-09-24 : un calcul en bac à sable n'écrit pas la fiche."""
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_by_id.return_value = {"id": EMPLOYEE_ID, "salaire_de_base": {"valeur": 2200}}
    mock_repo.get_salary_history.return_value = [_timeline_entry("2026-03-01", 2000, 2200)]
    mock_repo.salaire_de_base_a_date.return_value = {"valeur": 2200}

    prepare_salary_evolution_for_payslip(EMPLOYEE_ID, COMPANY_ID, 2026, 6, persister=False)

    mock_sync.assert_not_called()
    mock_repo.update.assert_not_called()


@patch("app.modules.payroll.application.salary_evolution_payroll._lire_bulletins_anterieurs", return_value=[])
@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_bac_a_sable_calcule_sur_la_fiche_synchronisee(mock_repo_cls, mock_sync, mock_lire):
    """Sans historique, le repli est le salaire de la fiche : en bac à sable,
    c'est celui que la synchronisation y aurait écrit, pas l'ancien."""
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_by_id.return_value = {"id": EMPLOYEE_ID, "salaire_de_base": {"valeur": 2000}}
    mock_repo.get_salary_history.return_value = []
    mock_repo.salaire_de_base_a_date.return_value = {"valeur": 3000}

    result = prepare_salary_evolution_for_payslip(EMPLOYEE_ID, COMPANY_ID, 2026, 8, persister=False)

    mock_repo.salaire_de_base_a_date.assert_called_once_with(EMPLOYEE_ID, COMPANY_ID, date.today())
    assert result["salaire_de_base"]["valeur"] == 3000.0


@patch("app.modules.payroll.application.salary_evolution_payroll._lire_bulletins_anterieurs", return_value=[])
@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_bac_a_sable_sans_calcul_garde_la_fiche(mock_repo_cls, mock_sync, mock_lire):
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_by_id.return_value = {"id": EMPLOYEE_ID, "salaire_de_base": {"valeur": 2000}}
    mock_repo.get_salary_history.return_value = []
    mock_repo.salaire_de_base_a_date.return_value = None

    result = prepare_salary_evolution_for_payslip(EMPLOYEE_ID, COMPANY_ID, 2026, 8, persister=False)

    assert result["salaire_de_base"]["valeur"] == 2000.0
```

- [ ] **Step 2 : vérifier l'échec**

Run: `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key .venv/bin/python -m pytest tests/unit/payroll/test_salary_evolution_payroll.py -q`
Expected: 3 FAIL — `TypeError: prepare_salary_evolution_for_payslip() got an unexpected keyword argument 'persister'` ; les tests existants PASS.

- [ ] **Step 3 : ajouter `persister`**

Dans `salary_evolution_payroll.py`, remplacer le début de la fonction (signature, docstring, synchronisation, relecture) par :

```python
def prepare_salary_evolution_for_payslip(
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
    persister: bool = True,
) -> Dict[str, Any]:
    """
    Synchronise le salaire actif et construit evolution_salaire_mois pour contrat.json.

    En bac à sable (`persister=False`), rien n'est écrit : la fiche relue reçoit
    en mémoire le salaire que la synchronisation y aurait écrit, pour que le
    calcul reste celui d'une vraie génération (spec 2026-09-24).
    """
    repo = EmployeeRepository()
    if persister:
        sync_employee_salaire_actif(employee_id, company_id, date.today())

    emp = repo.get_by_id(employee_id, company_id)
    if emp is None:
        return {}
    if not persister:
        synchronise = repo.salaire_de_base_a_date(employee_id, company_id, date.today())
        if synchronise is not None:
            emp = {**emp, "salaire_de_base": synchronise}
```

La suite de la fonction (`timeline = repo.get_salary_history(...)` et au-delà) est inchangée.

- [ ] **Step 4 : câbler les deux générateurs**

`payslip_generator.py`, l'appel existant devient :

```python
            salary_evo = prepare_salary_evolution_for_payslip(
                employee_id, str(company_id), year, month,
                persister=bac_a_sable is None,
            )
```

`payslip_generator_forfait.py`, même modification :

```python
            salary_evo = prepare_salary_evolution_for_payslip(
                employee_id, str(company_id), year, month,
                persister=bac_a_sable is None,
            )
```

- [ ] **Step 5 : vérifier**

Run: `cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key .venv/bin/python -m pytest tests/unit -q -p no:cacheprovider`
Expected: tout PASS (6 277 + 7 nouveaux).

Run: `cd backend && .venv/bin/python -m ruff check app/modules/payroll/application/salary_evolution_payroll.py tests/unit/payroll/test_salary_evolution_payroll.py`
Expected: aucune erreur nouvelle.

- [ ] **Step 6 : commit**

```bash
git add backend/app/modules/payroll/application/salary_evolution_payroll.py backend/app/modules/payroll/documents/payslip_generator.py backend/app/modules/payroll/documents/payslip_generator_forfait.py backend/tests/unit/payroll/test_salary_evolution_payroll.py
git commit -m "fix(paie): le bac a sable ne reecrit plus le salaire de la fiche"
```

---

### Task 3 : vérifier sur la base de test, sans rien écrire, et consigner

**Files:**
- Create (bloc-notes, hors dépôt) : `verif_bac_a_sable_etanche.py`
- Modify: `docs/colorplast-reprise-passation.md` (section « Brouillons d'août recalculés en bac à sable (24/09) »)
- Modify: mémoire `bac-a-sable-generation.md`

- [ ] **Step 1 : le script piège toutes les écritures**

Piéger `update/upsert/insert/delete` de `postgrest._sync.request_builder.SyncRequestBuilder` (journal de la pile, puis exception) **avant** tout import applicatif, puis :

- pour les six salariés de Colorplast en août : `payslip_generator_provider.generate_en_bac_a_sable(emp, 2026, 8, cumuls_precedents=<cumuls de juillet>)` et comparer brut, net, `structure_cotisations.total_salarial/total_patronal`, cumul brut au relevé du 24/09 (`aout_bac_a_sable.json`, version « nouvelle ») ;
- pour un salarié de Cartol Industrie avec `is_forfait_jour = true` : `process_payslip_generation_forfait(employee_id=..., year=2026, month=8, bac_a_sable=BacASable())`, appelé directement (le routage par statut l'enverrait aux heures).

Expected : **0 écriture interceptée** ; montants Colorplast identiques au centime. Pour le forfait, si le calcul s'arrête avant `prepare_salary_evolution_for_payslip` faute de données, le noter.

- [ ] **Step 2 : consigner**

Passation : la fuite est corrigée (commit), le résultat de la vérification, et
le constat hors périmètre de la spec (routage forfait par le seul libellé du
statut) ajouté aux défauts connus. Mémoire `bac-a-sable-generation` : remplacer le paragraphe « Pas étanche » par « corrigé le 24/09, vérifié à zéro écriture ».

- [ ] **Step 3 : commit**

```bash
git add docs/colorplast-reprise-passation.md docs/superpowers/specs/2026-09-24-bac-a-sable-sans-synchro-salaire-design.md docs/superpowers/plans/2026-09-24-bac-a-sable-sans-synchro-salaire.md
git commit -m "docs(paie): bac a sable etanche, spec, plan et verification"
```
