"""La revue du mois range les salariés comme le PDF et met les critiques d'abord."""

from __future__ import annotations

import pytest

from app.modules.payslips.domain.revue_du_mois import revue_du_mois

pytestmark = pytest.mark.unit


def _personne(identifiant: str, prenom: str, nom: str, **payslip_data) -> dict:
    return {
        "identifiant": identifiant,
        "prenom": prenom,
        "nom": nom,
        "payslip_data": {"salaire_brut": 1000.0, "calcul_du_brut": [{"libelle": "Salaire", "gain": 1000.0}], **payslip_data},
    }


def test_un_mois_juste_ne_donne_personne():
    assert revue_du_mois([_personne("a", "Ada", "Bernard")]) == []


def test_l_ordre_est_celui_du_pdf_et_les_critiques_passent_devant():
    avertie = _personne(
        "a",
        "Ada",
        "Martin",
        alertes_baremes=[{"code": "note_de_taux", "critique": False, "message": "Un taux est à relire."}],
    )
    decale = _personne(
        "b",
        "Léo",
        "Bernard",
        salaire_brut=1000.02,
        alertes_baremes=[
            {"code": "note_de_taux", "critique": False, "message": "Un taux est à relire."}
        ],
    )
    revues = revue_du_mois([avertie, decale])
    assert [revue.nom for revue in revues] == ["Bernard", "Martin"]
    niveaux = [alerte.level for alerte in revues[0].alertes]
    assert niveaux == ["CRITIQUE", "AVERTISSEMENT"]
    assert revues[0].alertes[0].rule_id == "B02"
    assert revues[0].alertes[1].rule_id == "note_de_taux"


def test_une_alerte_acquittee_sort_de_la_revue():
    personne = _personne(
        "b",
        "Léo",
        "Bernard",
        salaire_brut=1000.02,
        alerts_status={"B02": {"status": "acquittee", "comment": "Vu"}},
    )
    assert revue_du_mois([personne]) == []
