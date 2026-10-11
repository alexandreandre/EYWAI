"""Tests ICCP à la sortie (calculer_indemnite_conges_restants)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.payroll.engine.calcul_indemnites_sortie import (
    calculer_indemnite_conges_restants,
)
from app.modules.payroll.engine.cp_solde_sortie import CpSoldeSortie
from app.modules.payroll.engine.iccp_fin_contrat import (
    PeriodeConges,
    indemnite_fin_de_contrat,
    valeur_jour_maintien,
)
from app.modules.payroll.engine.reference_remuneration import ReferenceRemunerationResult

# Les tests du repli (sans compteurs de congés par période) : l'estimation
# globale d'avant, sans la « règle L1243-8 ».
SANS_PERIODES = patch(
    "app.modules.payroll.engine.calcul_indemnites_sortie._conges_par_periode_a_la_sortie",
    new=lambda *a, **k: None,
)


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


@SANS_PERIODES
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


@SANS_PERIODES
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


@SANS_PERIODES
@patch("app.modules.payroll.engine.calcul_indemnites_sortie.estimer_extras_fin_contrat")
@patch("app.modules.payroll.engine.calcul_indemnites_sortie.lire_brut_total_contrat")
@patch("app.modules.absences.infrastructure.leave_settings_repository.get_leave_policy")
@patch("app.modules.payroll.engine.calcul_indemnites_sortie.calculer_base_reference_dixieme")
@patch("app.modules.payroll.engine.calcul_indemnites_sortie.get_cp_solde_a_la_sortie")
def test_iccp_cdd_sans_compteurs_dixieme_de_la_remuneration_du_contrat(
    mock_solde, mock_ref, mock_policy, mock_brut_contrat, mock_extras
):
    """Repli d'une fin de CDD sans compteurs : le dixième de toute la
    rémunération du contrat, précarité comprise — le repli du bulletin
    (« dixieme_global »). Ce n'est pas l'article L1243-8, qui est la précarité."""
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

    assert res["montant"] == pytest.approx(1210.0, abs=0.01)
    assert res["details"]["methode_retenue"] == "dixieme_global"
    assert "iccp_l1243_8" not in res["details"]
    assert "L1243" not in res["calcul"]
    mock_extras.assert_called_once()


# --- Règle par période (engine/iccp_fin_contrat), celle du bulletin ----------


def _fiche_39h(contract_type: str = "CDI", hire_date: str = "2021-08-23") -> dict:
    return {
        "id": "emp-1",
        "company_id": "co-1",
        "hire_date": hire_date,
        "contract_type": contract_type,
        "salaire_de_base": {"valeur": 2374.55},
        "duree_hebdomadaire": 39,
        "specificites_paie": {"salaire_hors_hs_structurelles": True},
    }


# Valeur d'un jour au maintien à 39 h, salaire hors HS structurelles :
# taux 2 374,55 / 151,67 ; 7 h de base + 0,8 h majorée de 25 %.
VALEUR_JOUR_39H = valeur_jour_maintien(2374.55 / 151.67, 39, 0.25)


@patch("app.modules.absences.infrastructure.leave_settings_repository.get_leave_policy")
@patch("app.modules.payroll.engine.calcul_indemnites_sortie._conges_par_periode_a_la_sortie")
def test_demission_l_estimation_suit_la_regle_par_periode_du_bulletin(mock_periodes, mock_policy):
    """Démission d'un CDI au 30/09 : le dossier estimait 2 337,29 (maintien
    global) quand le bulletin versait 2 867,77 (par période)."""
    mock_policy.return_value.cp_reference_period_start_month = 6
    mock_periodes.return_value = {
        "periode_precedente": {"libelle": "2025-2026", "brut": 36000.0, "droits": 30.0, "restants": 15.0},
        "periode_en_cours": {"libelle": "2026-2027", "brut_avant_mois": 9300.0, "droits": 10.0, "restants": 10.0},
    }
    res = calculer_indemnite_conges_restants(
        _fiche_39h(), {"last_working_day": "2026-09-30", "exit_type": "demission"},
        supabase_client=MagicMock(),
    )
    # Mois de sortie estimé au salaire habituel (base + 17,33 h majorées), mois entier.
    mois = round(2374.55 + 17.33 * 2374.55 / 151.67 * 1.25, 2)
    attendu = indemnite_fin_de_contrat(
        [
            PeriodeConges("2025-2026", 36000.0, 30.0, 15.0),
            PeriodeConges("2026-2027", round(9300.0 + mois, 2), 10.0, 10.0),
        ],
        taux=0.1,
        valeur_jour=VALEUR_JOUR_39H,
    )
    assert res["montant"] == pytest.approx(attendu.total, abs=0.01)
    assert res["jours_restants"] == 25.0
    assert res["details"]["methode_retenue"] == "par_periode"
    assert res["details"]["mention"] == attendu.mention
    assert res["calcul"] == attendu.mention
    assert "L1243" not in str(res)


@patch("app.modules.payroll.engine.calcul_indemnites_sortie.estimer_extras_fin_contrat")
@patch("app.modules.payroll.engine.calcul_indemnites_sortie.lire_brut_total_contrat")
@patch("app.modules.absences.infrastructure.leave_settings_repository.get_leave_policy")
@patch("app.modules.payroll.engine.calcul_indemnites_sortie._conges_par_periode_a_la_sortie")
def test_fin_de_cdd_l_estimation_suit_la_regle_par_periode_precarite_comprise(
    mock_periodes, mock_policy, mock_brut_contrat, mock_extras
):
    """Fin de CDD au 11/09 : le dossier estimait 10 % de tout le contrat sans
    retirer les jours déjà pris (« L1243-8 ») ; la règle est celle du bulletin,
    sur les jours restants, précarité comprise dans le brut de la période."""
    mock_policy.return_value.cp_reference_period_start_month = 6
    mock_periodes.return_value = {
        "periode_en_cours": {"libelle": "2026-2027", "brut_avant_mois": 1000.0, "droits": 2.5, "restants": 2.0},
    }
    mock_brut_contrat.return_value = (1891.15, [])
    mock_extras.return_value = (189.12, 0.0)
    res = calculer_indemnite_conges_restants(
        _fiche_39h("CDD", "2026-08-24"),
        {"last_working_day": "2026-09-11", "exit_type": "fin_cdd"},
        supabase_client=MagicMock(),
    )
    mois = round((2374.55 + 17.33 * 2374.55 / 151.67 * 1.25) * 11 / 30, 2)
    attendu = indemnite_fin_de_contrat(
        [PeriodeConges("2026-2027", round(1000.0 + mois + 189.12, 2), 2.5, 2.0)],
        taux=0.1,
        valeur_jour=VALEUR_JOUR_39H,
    )
    assert res["montant"] == pytest.approx(attendu.total, abs=0.01)
    assert res["details"]["methode_retenue"] == "par_periode"
    assert res["details"]["prime_precarite_incluse"] == 189.12
    assert "L1243" not in str(res)


@patch("app.modules.absences.infrastructure.leave_settings_repository.get_leave_policy")
@patch("app.modules.payroll.engine.calcul_indemnites_sortie._conges_par_periode_a_la_sortie")
def test_sans_jour_restant_l_estimation_est_nulle(mock_periodes, mock_policy):
    mock_policy.return_value.cp_reference_period_start_month = 6
    mock_periodes.return_value = {
        "periode_en_cours": {"libelle": "2026-2027", "brut_avant_mois": 1000.0, "droits": 2.5, "restants": 0.0},
    }
    res = calculer_indemnite_conges_restants(
        _fiche_39h(), {"last_working_day": "2026-09-30"}, supabase_client=MagicMock()
    )
    assert res["montant"] == 0.0
    assert res["jours_restants"] == 0.0


def test_iccp_sans_hire_date():
    res = calculer_indemnite_conges_restants(
        {"salaire_de_base": {"valeur": 2000}}, _exit_data()
    )
    assert res["montant"] == 0.0
    assert "embauche" in res["calcul"].lower()
