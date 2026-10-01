"""État du report d'un net négatif sur le mois suivant, tel que l'écran le lit."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.modules.payslips.application.report_nap_negatif import construire_etat_du_report

META_SEPTEMBRE = {"company_id": "co-1", "employee_id": "emp-1", "year": 2026, "month": 9}


def _etat(net=-115.43, saisies=(), statut_suivant=None, cloture=False, meta=META_SEPTEMBRE):
    return construire_etat_du_report(
        "ps-1",
        meta,
        net_a_payer=net,
        saisies_mois_suivant=list(saisies),
        statut_bulletin_suivant=statut_suivant,
        mois_suivant_cloture=cloture,
    )


def test_sans_report_l_etat_donne_le_montant_et_le_mois_suivant():
    etat = _etat()
    assert etat["montant_a_reporter"] == 115.43
    assert (etat["annee_suivante"], etat["mois_suivant"]) == (2026, 10)
    assert etat["nom_du_report"] == "Report NAP négatif 09/2026"
    assert etat["saisie"] is None
    assert etat["verrou"] is None
    assert etat["company_id"] == "co-1"


def test_le_report_existant_est_retrouve_par_son_marqueur():
    etat = _etat(
        saisies=[
            {"id": "s-1", "name": "Acompte", "amount": -300.0, "sur_le_net": True},
            {"id": "s-2", "name": "Mon report", "amount": -100.0, "catalog_prime_id": "report_nap_negatif"},
        ]
    )
    assert etat["saisie"] == {"id": "s-2", "name": "Mon report", "amount": -100.0}


def test_le_report_d_un_autre_mois_n_est_pas_celui_de_ce_bulletin():
    etat = _etat(saisies=[{"id": "s-3", "name": "Report NAP négatif 08/2026", "amount": -50.0}])
    assert etat["saisie"] is None


def test_decembre_reporte_sur_janvier():
    etat = _etat(meta={**META_SEPTEMBRE, "month": 12})
    assert (etat["annee_suivante"], etat["mois_suivant"]) == (2027, 1)
    assert etat["nom_du_report"] == "Report NAP négatif 12/2026"


@pytest.mark.parametrize(
    ("statut", "cloture", "verrou"),
    [("valide", False, "bulletin_valide"), (None, True, "mois_cloture"), ("brouillon", False, None)],
)
def test_le_verrou_dit_pourquoi_on_ne_peut_plus_reporter(statut, cloture, verrou):
    assert _etat(statut_suivant=statut, cloture=cloture)["verrou"] == verrou


def test_un_net_positif_n_a_rien_a_reporter():
    assert _etat(net=12.0)["montant_a_reporter"] == 0.0


def test_la_route_masque_un_bulletin_d_une_autre_societe():
    from app.modules.payslips.api.router import get_report_net_negatif_route

    user = SimpleNamespace(active_company_id="co-1")
    with patch(
        "app.modules.payslips.api.router.get_payslip_meta_for_access",
        return_value={"company_id": "co-2", "employee_id": "emp-2", "year": 2026, "month": 9},
    ):
        with pytest.raises(HTTPException) as exc:
            get_report_net_negatif_route("ps-1", current_user=user)
    assert exc.value.status_code == 404
