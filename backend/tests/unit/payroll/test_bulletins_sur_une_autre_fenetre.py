"""Un bulletin garde la fenêtre sur laquelle il a été calculé (en-tête). Quand la
fenêtre du mois change, ces bulletins sont à régénérer — on les nomme."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.shared.domain.periode_variables import FenetreVariables

pytestmark = pytest.mark.unit

MODULE = "app.modules.payroll.application.periode_variables_service"
FENETRE = FenetreVariables(debut=date(2026, 6, 22), fin=date(2026, 7, 26), origine="regle")


def test_un_bulletin_calcule_sur_la_meme_fenetre_n_est_pas_a_regenerer():
    from app.modules.payroll.application.periode_variables_service import bulletin_hors_fenetre

    assert bulletin_hors_fenetre({"debut": "2026-06-22", "fin": "2026-07-26"}, FENETRE) is False


def test_un_bulletin_calcule_sur_une_autre_fin_est_a_regenerer():
    from app.modules.payroll.application.periode_variables_service import bulletin_hors_fenetre

    assert bulletin_hors_fenetre({"debut": "2026-06-22", "fin": "2026-07-19"}, FENETRE) is True


def test_un_bulletin_sans_fenetre_en_en_tete_ou_importe_est_ignore():
    from app.modules.payroll.application.periode_variables_service import bulletin_hors_fenetre

    assert bulletin_hors_fenetre({"debut": None, "fin": None}, FENETRE) is False
    assert (
        bulletin_hors_fenetre(
            {"debut": "2026-06-01", "fin": "2026-06-30", "origine": "importe"}, FENETRE
        )
        is False
    )


@patch(f"{MODULE}.supabase")
def test_le_service_lit_les_bulletins_du_mois_et_rend_ceux_a_regenerer(mock_supabase):
    from app.modules.payroll.application.periode_variables_service import (
        bulletins_sur_une_autre_fenetre,
    )

    chaine = mock_supabase.table.return_value.select.return_value.match.return_value
    chaine.execute.return_value = MagicMock(
        data=[
            {"employee_id": "e1", "status": "brouillon", "origine": "calcule", "debut": "2026-06-22", "fin": "2026-07-19"},
            {"employee_id": "e2", "status": "valide", "origine": "calcule", "debut": "2026-06-22", "fin": "2026-07-26"},
            {"employee_id": "e3", "status": "valide", "origine": "importe", "debut": None, "fin": None},
        ]
    )

    lignes = bulletins_sur_une_autre_fenetre("c1", 2026, 7, FENETRE)

    assert [ligne["employee_id"] for ligne in lignes] == ["e1"]
    select = mock_supabase.table.return_value.select.call_args.args[0]
    assert "payslip_data->en_tete->>date_debut_variables" in select


@patch(f"{MODULE}.bulletins_sur_une_autre_fenetre")
@patch(f"{MODULE}.resoudre_fenetre_variables", return_value=FENETRE)
def test_l_apercu_compte_les_bulletins_a_regenerer(mock_fenetre, mock_bulletins):
    from app.modules.payroll.application.periode_variables_service import apercu_fenetre

    mock_bulletins.return_value = [{"employee_id": "e1"}, {"employee_id": "e4"}]

    apercu = apercu_fenetre("c1", 2026, 7)

    assert apercu["bulletins_a_regenerer"] == 2
    assert apercu["employes_a_regenerer"] == ["e1", "e4"]
