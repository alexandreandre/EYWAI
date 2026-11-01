"""Un mois à deux contrats [D3] : l'état « À recalculer » est celui du bulletin
du contrat de la fiche, jamais celui du contrat rangé.

Rejeu de H.5 sur le site de test, 01/11/2026 : le bulletin du CDI, à peine
généré, passait « À recalculer — la fiche a changé ». L'état se range par mois ;
le bulletin du CDD rangé, lu dans la même liste, comparait sa fiche (celle du
CDD) à la fiche d'aujourd'hui (le CDI) et écrasait l'état du mois.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payroll.application.empreinte_entrees_service import (
    annoter_a_recalculer,
    empreinte_des_lectures,
    etat_dans_la_chaine,
)
from app.modules.payroll.infrastructure.empreinte_entrees_queries import (
    _EMPREINTES_DES_BULLETINS,
    LecturesEmpreinte,
)

pytestmark = pytest.mark.unit

_SERVICE = "app.modules.payroll.application.empreinte_entrees_service"

EMPLOYEE = {
    "salaire_de_base": {"montant": 2100},
    "duree_hebdomadaire": 35,
    "statut": "Non-Cadre",
    "is_forfait_jour": False,
}
COMPANY = {"idcc": "292", "taux_at_mp": 1.2, "settings": {}}
CALENDRIERS = {
    (2026, 10): {
        "planned_calendar": {"calendrier_prevu": [{"jour": 20, "type": "travail", "heures": 7}]},
        "actual_hours": {"calendrier_reel": [{"jour": 20, "type": "travail", "heures": 7}]},
    },
}


def _lectures() -> LecturesEmpreinte:
    return LecturesEmpreinte(
        employee=EMPLOYEE,
        company=COMPANY,
        calendriers=CALENDRIERS,
        absences=[],
        saisies_par_mois={},
        notes_de_frais=[],
    )


def _hash_du_cdi() -> str:
    return empreinte_des_lectures(
        year=2026, month=10, calendriers=CALENDRIERS, absences=[], saisies=[],
        employee=EMPLOYEE, company=COMPANY, notes_de_frais=[],
    )


def _lignes(range_en_dernier: bool) -> list[dict]:
    cdi = {"id": "cdi", "year": 2026, "month": 10, "status": "brouillon",
           "origine": "calcule", "empreinte_entrees": _hash_du_cdi()}
    cdd = {"id": "cdd", "year": 2026, "month": 10, "status": "brouillon",
           "origine": "calcule", "empreinte_entrees": "0" * 64, "contract_period_id": "periode-cdd"}
    return [cdi, cdd] if range_en_dernier else [cdd, cdi]


@pytest.mark.parametrize("range_en_dernier", [True, False])
def test_le_bulletin_du_cdi_reste_a_jour_a_cote_du_bulletin_range(range_en_dernier):
    with patch(f"{_SERVICE}.lire_lectures_salarie", return_value=_lectures()):
        lignes = annoter_a_recalculer("e1", _lignes(range_en_dernier))

    par_id = {l["id"]: l for l in lignes}
    assert par_id["cdi"]["a_recalculer"] is False
    assert par_id["cdi"]["raison_a_recalculer"] is None
    # Le bulletin du contrat rangé se régénère sur demande, depuis sa page : rien à signaler.
    assert par_id["cdd"]["a_recalculer"] is None


def test_l_etat_du_mois_est_celui_du_bulletin_de_la_fiche():
    with patch(f"{_SERVICE}.lire_lectures_salarie", return_value=_lectures()), patch(
        f"{_SERVICE}.lire_empreintes_des_bulletins", return_value=_lignes(range_en_dernier=True)
    ):
        etat = etat_dans_la_chaine("e1", 2026, 10)

    assert etat is not None and etat.a_recalculer is False


def test_la_lecture_des_empreintes_dit_le_contrat_du_bulletin():
    assert "contract_period_id" in _EMPREINTES_DES_BULLETINS


def test_la_page_du_bulletin_range_ne_prend_pas_l_etat_du_mois():
    from app.modules.payslips.application import service

    detail = {"employee_id": "e1", "year": 2026, "month": 10, "contract_period_id": "periode-cdd"}
    with patch(f"{_SERVICE}.etat_dans_la_chaine") as etat:
        assert service._etats_du_bulletin(detail)[0] is None
    etat.assert_not_called()


def test_la_validation_du_bulletin_range_ne_lit_pas_l_etat_du_mois():
    from app.modules.payslips.application import comparison_service

    detail = {"employee_id": "e1", "year": 2026, "month": 10, "contract_period_id": "periode-cdd"}
    with patch(f"{_SERVICE}.etat_dans_la_chaine") as etat:
        assert comparison_service._etat_actuel_du_bulletin(detail) is None
    etat.assert_not_called()
