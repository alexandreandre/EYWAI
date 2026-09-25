"""Tests prepare_salary_evolution_for_payslip — résolution avant génération bulletin."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.payroll.application.salary_evolution_payroll import (
    prepare_salary_evolution_for_payslip,
)

pytestmark = pytest.mark.unit

EMPLOYEE_ID = "emp-salary-evo"
COMPANY_ID = "co-salary-evo"


def _timeline_entry(eff: str, ancien: float, nouveau: float) -> dict:
    return {
        "effective_date": eff,
        "ancien_salaire": {"valeur": ancien},
        "nouveau_salaire": {"valeur": nouveau},
    }


@patch("app.modules.payroll.application.salary_evolution_payroll._lire_bulletins_anterieurs", return_value=[])
@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_prepare_prorata_mi_mois(mock_repo_cls, mock_sync, mock_lire):
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_by_id.return_value = {
        "id": EMPLOYEE_ID,
        "salaire_de_base": {"valeur": 2600, "devise": "EUR"},
    }
    mock_repo.get_salary_history.return_value = [
        _timeline_entry("2026-06-09", 2600, 2678),
    ]

    result = prepare_salary_evolution_for_payslip(
        EMPLOYEE_ID, COMPANY_ID, 2026, 6
    )

    mock_sync.assert_called_once_with(EMPLOYEE_ID, COMPANY_ID, date.today())
    attendu = round((2600 * 8 / 30) + (2678 * 22 / 30), 2)
    assert result["salaire_de_base"]["valeur"] == pytest.approx(attendu, abs=0.02)
    evo = result["evolution_salaire_mois"]
    assert evo["prorata"] is not None
    assert evo["prorata"]["jours_ancien"] == 8
    assert evo["rappel"]["montant"] == 0.0


@patch("app.modules.payroll.application.salary_evolution_payroll._lire_bulletins_anterieurs", return_value=[])
@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_prepare_rappel_et_salaire_plein(mock_repo_cls, mock_sync, mock_lire):
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_by_id.return_value = {
        "id": EMPLOYEE_ID,
        "salaire_de_base": {"valeur": 2200},
    }
    mock_repo.get_salary_history.return_value = [
        _timeline_entry("2026-03-01", 2000, 2200),
    ]
    # Mars à mai payés à l'ancien taux : le rappel est dû.
    mock_lire.return_value = [
        {"year": 2026, "month": m, "parametres": {"salaire_base_mensuel": 2000.0}, "calcul_du_brut": []}
        for m in (3, 4, 5)
    ]

    result = prepare_salary_evolution_for_payslip(
        EMPLOYEE_ID, COMPANY_ID, 2026, 6
    )

    assert result["salaire_de_base"]["valeur"] == 2200.0
    assert result["evolution_salaire_mois"]["rappel"]["montant"] == pytest.approx(
        600.0, abs=0.02
    )


@patch("app.modules.payroll.application.salary_evolution_payroll._lire_bulletins_anterieurs", return_value=[])
@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_prepare_date_future_n_impacte_pas_bulletin(mock_repo_cls, mock_sync, mock_lire):
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_by_id.return_value = {
        "id": EMPLOYEE_ID,
        "salaire_de_base": {"valeur": 2200},
    }
    mock_repo.get_salary_history.return_value = [
        _timeline_entry("2026-07-01", 2200, 2500),
    ]

    result = prepare_salary_evolution_for_payslip(
        EMPLOYEE_ID, COMPANY_ID, 2026, 6
    )

    assert result["salaire_de_base"]["valeur"] == 2200.0
    assert result["evolution_salaire_mois"]["prorata"] is None
    assert result["evolution_salaire_mois"]["rappel"]["montant"] == 0.0


@patch("app.modules.payroll.application.salary_evolution_payroll._lire_bulletins_anterieurs", return_value=[])
@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_prepare_employe_introuvable(mock_repo_cls, mock_sync, mock_lire):
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_by_id.return_value = None

    result = prepare_salary_evolution_for_payslip(
        EMPLOYEE_ID, COMPANY_ID, 2026, 6
    )

    assert result == {}
    mock_sync.assert_called_once()


@patch("app.modules.payroll.application.salary_evolution_payroll._lire_bulletins_anterieurs")
@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_pas_de_rappel_pour_un_mois_deja_paye_au_nouveau_taux(mock_repo_cls, mock_sync, mock_lire):
    """Demory (Colorplast) : SMIC revalorisé au 01/06 enregistré après coup,
    juin déjà payé 1 867,06. Le bulletin de juillet ne rappelle rien."""
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_by_id.return_value = {
        "id": EMPLOYEE_ID,
        "salaire_de_base": {"valeur": 1867.06},
        "duree_hebdomadaire": 39,
    }
    mock_repo.get_salary_history.return_value = [
        _timeline_entry("2026-03-23", 0, 1850.37),
        _timeline_entry("2026-06-01", 1850.37, 1867.06),
    ]
    # Bulletin de juin antérieur au champ mémorisé : relu depuis le taux horaire.
    mock_lire.return_value = [
        {
            "year": 2026, "month": 6, "parametres": {"smic_horaire": 12.31},
            "calcul_du_brut": [{"libelle": "Salaire de base", "quantite": 151.67, "taux": 12.31, "gain": 1867.06}],
        },
        {
            "year": 2026, "month": 5, "parametres": {},
            "calcul_du_brut": [{"libelle": "Salaire de base", "quantite": 151.67, "taux": 12.2, "gain": 1850.37}],
        },
    ]

    result = prepare_salary_evolution_for_payslip(EMPLOYEE_ID, COMPANY_ID, 2026, 7)

    assert result["evolution_salaire_mois"]["rappel"]["montant"] == 0.0
    assert result["salaire_de_base"]["valeur"] == 1867.06


@patch("app.modules.payroll.application.salary_evolution_payroll._lire_bulletins_anterieurs")
@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_lecture_des_bulletins_en_echec_garde_le_comportement_historique(
    mock_repo_cls, mock_sync, mock_lire
):
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_by_id.return_value = {"id": EMPLOYEE_ID, "salaire_de_base": {"valeur": 2200}}
    mock_repo.get_salary_history.return_value = [_timeline_entry("2026-03-01", 2000, 2200)]
    mock_lire.side_effect = RuntimeError("base injoignable")

    result = prepare_salary_evolution_for_payslip(EMPLOYEE_ID, COMPANY_ID, 2026, 6)

    assert result["evolution_salaire_mois"]["rappel"]["montant"] == pytest.approx(600.0, abs=0.02)


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
