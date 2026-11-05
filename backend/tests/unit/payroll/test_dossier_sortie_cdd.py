"""Dossier de départ d'un CDD : la prime et les congés estimés selon la loi.

- Prime (L1243-8, service-public F40) : la rémunération versée durant le
  contrat, mois de sortie estimé au salaire.
- Congés (L1242-16, fiche service-public « Indemnité compensatrice de congés
  payés », exemple (18 300 + 1 830)/10) : la prime n'entre dans la base que si
  elle est versée.
- Période en cours (L3141-24 I) : sans cumuls du mois précédent (mois repris de
  l'ancien logiciel), la somme des bulletins de la période.

Cas d'origine : CDD du 29/06 au 30/09/2026 à 3 000 €, juillet et août repris
sans cumuls.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.payroll.engine import calcul_indemnites_sortie as module
from app.modules.payroll.engine.calcul_indemnites_sortie import (
    _conges_par_periode_a_la_sortie,
    calculer_indemnite_conges_restants,
)

pytestmark = pytest.mark.unit

EMPLOYE = {
    "id": "emp-1",
    "company_id": "co-1",
    "hire_date": "2026-06-29",
    "contract_type": "CDD",
    "salaire_de_base": {"valeur": 3000.0},
    "duree_hebdomadaire": 35,
    "baremes": {"cdd": {"precarite": {"taux": 0.10}, "indemnite_conges": {"taux": 0.10}}},
}

COMPTEURS = {
    "conges_payes": {"pris": 0.0, "solde": 6.38, "periode": "01/06/2026 – 31/05/2027"},
    "conges_payes_periode_precedente": {"pris": 0.0, "solde": 0.0, "periode": "01/06/2025 – 31/05/2026"},
}

PERIODES = {
    "periode_en_cours": {"libelle": "2026-2027", "brut_avant_mois": 6272.73, "droits": 6.38, "restants": 6.38},
}


@patch.object(module, "_conges_par_periode_a_la_sortie", return_value=PERIODES)
@patch.object(module, "lire_brut_total_contrat", return_value=(9272.73, []))
def test_fin_de_cdd_la_prime_se_calcule_sur_le_contrat_mois_de_sortie_estime(mock_contrat, _):
    res = calculer_indemnite_conges_restants(
        EMPLOYE, {"last_working_day": "2026-09-30", "exit_type": "fin_cdd"}, supabase_client=MagicMock()
    )

    assert mock_contrat.call_args.kwargs["estimer_le_mois_de_sortie"] is True
    assert res["details"]["prime_precarite_incluse"] == 927.27
    # 6 272,73 + 3 000 (septembre estimé) + 927,27 = 10 200,00 → dixième 1 020,00
    assert res["montant"] == 1020.0


@patch.object(module, "_conges_par_periode_a_la_sortie", return_value=PERIODES)
@patch.object(module, "lire_brut_total_contrat", return_value=(9272.73, []))
def test_sans_prime_versee_la_base_des_conges_ne_la_compte_pas(_, __):
    res = calculer_indemnite_conges_restants(
        EMPLOYE,
        {"last_working_day": "2026-09-30", "exit_type": "fin_periode_essai"},
        supabase_client=MagicMock(),
    )

    assert res["details"]["prime_precarite_incluse"] == 0.0
    assert res["montant"] == 927.27  # 10 % de 9 272,73


@patch.object(module, "calculer_base_reference_dixieme")
@patch.object(module, "get_cp_solde_a_la_sortie", return_value=None)
@patch.object(module, "_conges_par_periode_a_la_sortie", return_value=None)
@patch.object(module, "lire_brut_total_contrat", return_value=(200.0, []))
def test_le_repli_est_borne_par_l_entree_et_la_sortie(_, __, ___, mock_ref):
    from app.modules.payroll.engine.reference_remuneration import ReferenceRemunerationResult

    mock_ref.return_value = ReferenceRemunerationResult(
        base_totale=200.0, periode_debut=date(2026, 6, 29), periode_fin=date(2026, 6, 30), periode_label="x"
    )
    with patch("app.modules.absences.infrastructure.leave_settings_repository.get_leave_policy") as policy:
        policy.return_value.cp_reference_period_start_month = 6
        calculer_indemnite_conges_restants(
            EMPLOYE, {"last_working_day": "2026-06-30", "exit_type": "fin_cdd"}, supabase_client=MagicMock()
        )

    assert mock_ref.call_args.kwargs["entree"] == date(2026, 6, 29)
    assert mock_ref.call_args.kwargs["sortie"] == date(2026, 6, 30)


@patch.object(module, "_cumuls_du_mois_precedent", return_value=None)
@patch("app.modules.absences.application.queries.get_absence_balances_for_payslip", return_value=COMPTEURS)
@patch("app.modules.payroll.documents.payslip_run_heures._brut_de_la_periode_precedente", return_value=None)
@patch.object(module, "bruts_du_contrat", return_value=(6272.73, 3, []))
def test_sans_cumuls_le_brut_avant_le_mois_est_la_somme_des_bulletins_de_la_periode(mock_bruts, *_):
    cfg = _conges_par_periode_a_la_sortie(
        "emp-1", date(2026, 9, 30), MagicMock(), entree=date(2026, 6, 29), salaire=3000.0
    )

    assert cfg["periode_en_cours"]["brut_avant_mois"] == 6272.73
    args = mock_bruts.call_args
    assert args.args[1:3] == (date(2026, 6, 29), date(2026, 8, 31))
    assert args.kwargs["estimer_le_dernier_mois"] is False


@patch.object(module, "calculer_base_reference_dixieme")
@patch.object(module, "get_cp_solde_a_la_sortie", return_value=None)
@patch.object(module, "_conges_par_periode_a_la_sortie", return_value=None)
@patch.object(module, "lire_brut_total_contrat", return_value=(200.0, []))
def test_le_repli_estime_au_salaire_habituel_comme_la_prime(_, __, ___, mock_ref):
    from app.modules.payroll.engine.reference_remuneration import ReferenceRemunerationResult

    mock_ref.return_value = ReferenceRemunerationResult(
        base_totale=0.0, periode_debut=date(2026, 6, 1), periode_fin=date(2026, 9, 30), periode_label="x"
    )
    employe_39h = {**EMPLOYE, "duree_hebdomadaire": 39}
    with (
        patch("app.modules.absences.infrastructure.leave_settings_repository.get_leave_policy") as policy,
        patch.object(module, "_salaire_habituel_et_taux_horaire", return_value=(3400.0, 20.0, 39.0)),
    ):
        policy.return_value.cp_reference_period_start_month = 6
        calculer_indemnite_conges_restants(
            employe_39h, {"last_working_day": "2026-09-30", "exit_type": "fin_cdd"}, supabase_client=MagicMock()
        )

    assert mock_ref.call_args.kwargs["salaire_contractuel_fallback"] == 3400.0
