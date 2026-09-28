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
