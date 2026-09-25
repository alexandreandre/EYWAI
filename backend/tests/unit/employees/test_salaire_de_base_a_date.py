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
