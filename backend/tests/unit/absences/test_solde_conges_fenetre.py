"""Le solde de congés imprimé suit la fenêtre des variables, comme le paiement.

Décision du 28/09/2026 : « congés dans la fenêtre des variables uniquement, pas
d'exception, mois d'après ». Un congé du 26/08, après l'arrêté du 23/08, est
payé sur le bulletin de septembre : il ne sort du solde qu'avec lui. Le solde
imprimé en bas du bulletin comptait jusqu'à la fin du mois civil.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.absences.application.queries import conges_jusqu_a

pytestmark = pytest.mark.unit


def test_les_conges_apres_la_fenetre_restent_au_solde():
    absences = [
        {"type": "conge_paye", "selected_days": ["2026-08-20", "2026-08-21", "2026-08-26"], "jours_payes": 3},
        {"type": "conge_paye", "selected_days": ["2026-08-27"]},
        {"type": "arret_maladie", "selected_days": ["2026-08-28"]},
    ]
    assert conges_jusqu_a(absences, date(2026, 8, 23)) == [
        {"type": "conge_paye", "selected_days": ["2026-08-20", "2026-08-21"], "jours_payes": 3},
        {"type": "arret_maladie", "selected_days": ["2026-08-28"]},
    ]


def test_sans_fenetre_rien_n_est_retire():
    absences = [{"type": "conge_paye", "selected_days": ["2026-08-26"]}]
    assert conges_jusqu_a(absences, None) == absences


def test_le_bulletin_passe_la_fin_de_sa_fenetre_au_solde():
    from app.modules.payroll.engine.bulletin import build_solde_conges_pied_de_page

    with patch(
        "app.modules.absences.application.queries.get_absence_balances_for_payslip",
        return_value={"conges_payes": 1},
    ) as soldes:
        build_solde_conges_pied_de_page("e1", 2026, 8, "2026-08-23")
    assert soldes.call_args.kwargs == {"date_fin_prises": date(2026, 8, 23)}


def test_rien_ne_s_acquiert_apres_la_sortie():
    """Fin de CDD au 15/09 : le solde du bulletin de septembre s'arrête au 15/09."""
    from app.modules.absences.application import queries as q

    vus = {}

    def cp(hire, validated, ref, **_):
        vus["ref"] = ref
        vus["pris_jusqu_a"] = max((d for a in validated for d in a.get("selected_days", [])), default=None)
        return {"periode_courante": {}, "periode_precedente": {}}

    with (
        patch.object(q, "_parse_hire_date", return_value=date(2026, 3, 23)),
        patch.object(q, "_date_de_sortie", return_value=date(2026, 9, 15)),
        patch.object(q, "_reprise_posterieure_au_bulletin", return_value=False),
        patch.object(q, "absence_repository") as repo,
        patch.object(q, "get_repos_credits_by_employee_year", return_value={}),
        patch.object(q, "_leave_context", return_value=(None, None, 0, None)),
        patch.object(q, "_cp_balance_extras", return_value={}),
        patch.object(q, "compute_cp_balances_for_bulletin", side_effect=cp),
        patch.object(q, "compute_absence_balances", return_value={"rtt": {}, "jtc": {}, "repos_compensateur": {}}),
        patch.object(q, "_get_employee_company_id", return_value=None),
        patch.object(q, "_hours_per_rest_day_for_employee", return_value=7.0),
    ):
        repo.list_validated_for_employees.return_value = [
            {"type": "conge", "selected_days": ["2026-09-10"]},
            {"type": "conge", "selected_days": ["2026-09-18"]},
        ]
        soldes = q.get_absence_balances_for_payslip("e1", 2026, 9, date_fin_prises=date(2026, 9, 20))
    assert vus["ref"] == date(2026, 9, 15)
    assert soldes["date_reference"] == "15/09/2026"
