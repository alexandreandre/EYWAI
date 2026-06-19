"""Tests ICCP à la sortie (calculer_indemnite_conges_restants)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.payroll.engine.calcul_indemnites_sortie import (
    calculer_indemnite_conges_restants,
)
from app.modules.payroll.engine.cp_solde_sortie import CpSoldeSortie
from app.modules.payroll.engine.reference_remuneration import ReferenceRemunerationResult


def _employee(salaire: float = 2200.0, contract_type: str = "CDI") -> dict:
    return {
        "id": "emp-1",
        "company_id": "co-1",
        "hire_date": "2020-01-15",
        "contract_type": contract_type,
        "salaire_de_base": {"valeur": salaire},
    }


def _exit_data() -> dict:
    return {"last_working_day": "2025-09-30"}


@patch("app.modules.absences.infrastructure.leave_settings_repository.get_leave_policy")
@patch("app.modules.payroll.engine.calcul_indemnites_sortie.calculer_base_reference_dixieme")
@patch("app.modules.payroll.engine.calcul_indemnites_sortie.get_cp_solde_a_la_sortie")
def test_iccp_sortie_maintien_gagne(mock_solde, mock_ref, mock_policy):
    mock_policy.return_value.cp_reference_period_start_month = 6
    mock_solde.return_value = CpSoldeSortie(
        jours_restants=8.0, conges_acquis=25.0, conges_pris=17.0
    )
    mock_ref.return_value = ReferenceRemunerationResult(
        base_totale=24000.0,
        periode_debut=date(2024, 6, 1),
        periode_fin=date(2025, 5, 31),
        periode_label="01/06/2024 – 31/05/2025",
    )

    res = calculer_indemnite_conges_restants(
        _employee(), _exit_data(), supabase_client=MagicMock()
    )

    assert res["jours_restants"] == 8.0
    assert res["details"]["methode_retenue"] == "maintien"
    assert res["montant"] == res["details"]["indemnite_maintien"]


@patch("app.modules.absences.infrastructure.leave_settings_repository.get_leave_policy")
@patch("app.modules.payroll.engine.calcul_indemnites_sortie.calculer_base_reference_dixieme")
@patch("app.modules.payroll.engine.calcul_indemnites_sortie.get_cp_solde_a_la_sortie")
def test_iccp_sortie_dixieme_gagne(mock_solde, mock_ref, mock_policy):
    mock_policy.return_value.cp_reference_period_start_month = 6
    mock_solde.return_value = CpSoldeSortie(
        jours_restants=10.0, conges_acquis=30.0, conges_pris=20.0
    )
    mock_ref.return_value = ReferenceRemunerationResult(
        base_totale=36000.0,
        periode_debut=date(2024, 6, 1),
        periode_fin=date(2025, 5, 31),
        periode_label="01/06/2024 – 31/05/2025",
    )

    res = calculer_indemnite_conges_restants(
        _employee(salaire=1800.0), _exit_data(), supabase_client=MagicMock()
    )

    assert res["details"]["methode_retenue"] == "dixieme"
    assert res["montant"] == res["details"]["indemnite_dixieme"]


@patch("app.modules.payroll.engine.calcul_indemnites_sortie.estimer_extras_fin_contrat")
@patch("app.modules.payroll.engine.calcul_indemnites_sortie.lire_brut_total_contrat")
@patch("app.modules.absences.infrastructure.leave_settings_repository.get_leave_policy")
@patch("app.modules.payroll.engine.calcul_indemnites_sortie.calculer_base_reference_dixieme")
@patch("app.modules.payroll.engine.calcul_indemnites_sortie.get_cp_solde_a_la_sortie")
def test_iccp_cdd_l1243_8(mock_solde, mock_ref, mock_policy, mock_brut_contrat, mock_extras):
    mock_policy.return_value.cp_reference_period_start_month = 6
    mock_solde.return_value = CpSoldeSortie(
        jours_restants=0.0, conges_acquis=0.0, conges_pris=0.0
    )
    mock_brut_contrat.return_value = (11000.0, [])
    mock_extras.return_value = (1100.0, 0.0)
    mock_ref.return_value = ReferenceRemunerationResult(
        base_totale=12100.0,
        periode_debut=date(2024, 6, 1),
        periode_fin=date(2025, 5, 31),
        periode_label="01/06/2024 – 31/05/2025",
        prime_precarite_incluse=1100.0,
    )

    res = calculer_indemnite_conges_restants(
        _employee(contract_type="CDD"),
        _exit_data(),
        supabase_client=MagicMock(),
    )

    assert res["details"]["iccp_l1243_8"] == pytest.approx(1210.0, abs=0.01)
    assert res["montant"] >= 1100.0
    mock_extras.assert_called_once()
    call_kw = mock_ref.call_args.kwargs
    assert call_kw["montant_precarite"] == 1100.0


def test_iccp_sans_hire_date():
    res = calculer_indemnite_conges_restants(
        {"salaire_de_base": {"valeur": 2000}}, _exit_data()
    )
    assert res["montant"] == 0.0
    assert "embauche" in res["calcul"].lower()
