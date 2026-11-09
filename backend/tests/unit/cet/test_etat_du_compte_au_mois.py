"""Compteur CET du bulletin : cumul au mois, mouvements validés seuls (R-376)."""

import pytest

from app.modules.cet.domain.rules import etat_du_compte_au_mois

pytestmark = pytest.mark.unit


def _mouvement(type_mouvement, *, hours=0.0, days=0.0, status="validated", year=2026, month=10):
    return {
        "movement_type": type_mouvement,
        "hours": hours,
        "days": days,
        "status": status,
        "year": year,
        "month": month,
    }


def test_depots_et_repos_en_heures():
    etat = etat_du_compte_au_mois(
        [
            _mouvement("deposit_hs", hours=14.0),
            _mouvement("deposit_cp", days=2.0, status="applied_payroll"),
            _mouvement("withdraw_rest", hours=7.0),
        ],
        2026,
        10,
    )
    assert etat == {"acquis": 28.0, "pris": 7.0, "solde": 21.0}


def test_un_mouvement_posterieur_au_bulletin_ne_compte_pas():
    etat = etat_du_compte_au_mois(
        [_mouvement("deposit_hs", hours=7.0, month=9), _mouvement("deposit_hs", hours=7.0, month=11)],
        2026,
        10,
    )
    assert etat == {"acquis": 7.0, "pris": 0.0, "solde": 7.0}


def test_une_demande_en_attente_ne_compte_pas():
    assert etat_du_compte_au_mois([_mouvement("deposit_hs", hours=7.0, status="pending")], 2026, 10) is None


def test_sans_mouvement_pas_de_compteur():
    assert etat_du_compte_au_mois([], 2026, 10) is None


def test_ajustement_negatif_compte_comme_pris():
    etat = etat_du_compte_au_mois(
        [_mouvement("deposit_hs", hours=10.0), _mouvement("adjustment", hours=-3.0)], 2026, 10
    )
    assert etat == {"acquis": 10.0, "pris": 3.0, "solde": 7.0}


def test_societe_sans_cet_rien_n_est_relu():
    from types import SimpleNamespace
    from unittest.mock import patch

    from app.modules.payroll.documents.payslip_run_heures import etat_cet_du_bulletin

    with patch("app.modules.cet.infrastructure.repository.list_movements_for_employee") as lecture:
        etat = etat_cet_du_bulletin(SimpleNamespace(alertes_baremes=[]), {"cet_enabled": False}, "e", 2026, 10, 7.0)
    assert etat is None
    lecture.assert_not_called()


def test_lecture_ratee_se_dit_a_la_rh():
    from types import SimpleNamespace
    from unittest.mock import patch

    from app.modules.payroll.documents.payslip_run_heures import etat_cet_du_bulletin

    contexte = SimpleNamespace(alertes_baremes=[])
    with patch(
        "app.modules.cet.infrastructure.repository.list_movements_for_employee", side_effect=RuntimeError("boom")
    ):
        etat = etat_cet_du_bulletin(contexte, {"cet_enabled": True}, "e", 2026, 10, 7.0)
    assert etat is None
    assert contexte.alertes_baremes[0]["code"] == "compteur_cet_illisible"
    assert contexte.alertes_baremes[0]["critique"] is False
