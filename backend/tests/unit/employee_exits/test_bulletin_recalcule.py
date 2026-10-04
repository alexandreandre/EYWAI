"""Un bulletin recalculé après les documents de sortie les met « à revoir ».

Le solde de tout compte reprend le bulletin du mois de sortie, l'attestation
employeur les salaires des mois d'avant ; tous deux sont figés en PDF à leur
génération. Corriger le bulletin ensuite laissait ces documents faux sans rien
dire. La note posée sur le départ suit le mécanisme déjà affiché à l'écran pour
un changement de type ou de date de départ.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.modules.employee_exits.application.bulletin_recalcule import (
    CLE_NOTE,
    signaler_bulletin_recalcule,
    types_tires_du_bulletin,
)

pytestmark = pytest.mark.unit

MAINTENANT = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


class TestTypesTiresDuBulletin:
    def test_le_mois_de_sortie_touche_le_solde_et_l_attestation(self):
        assert types_tires_du_bulletin("2026-09-15", 2026, 9) == [
            "attestation_pole_emploi",
            "solde_tout_compte",
        ]

    def test_un_mois_d_avant_ne_touche_que_l_attestation(self):
        assert types_tires_du_bulletin("2026-09-15", 2026, 6) == ["attestation_pole_emploi"]
        assert types_tires_du_bulletin("2026-09-15", 2024, 9) == ["attestation_pole_emploi"]

    def test_un_mois_apres_la_sortie_ou_trop_ancien_ne_touche_rien(self):
        assert types_tires_du_bulletin("2026-09-15", 2026, 10) == []
        assert types_tires_du_bulletin("2026-09-15", 2024, 8) == []
        assert types_tires_du_bulletin(None, 2026, 9) == []


def _depot(sorties, documents):
    exits = MagicMock()
    exits.list.return_value = sorties
    docs = MagicMock()
    docs.list_by_exit.side_effect = lambda exit_id, _c: documents.get(exit_id, [])
    return exits, docs


def _doc(type_, categorie="generated"):
    return {"document_type": type_, "document_category": categorie}


def test_le_bulletin_de_sortie_recalcule_met_le_solde_et_l_attestation_a_revoir():
    sortie = {"id": "x1", "status": "demission_effective", "last_working_day": "2026-09-15",
              "exit_notes": {"autre": {"garde": True}}}
    exits, docs = _depot(
        [sortie],
        {"x1": [_doc("solde_tout_compte"), _doc("attestation_pole_emploi"),
                _doc("certificat_travail"), _doc("solde_tout_compte", "uploaded")]},
    )
    signaler_bulletin_recalcule("e1", "c1", 2026, 9, exits=exits, documents=docs, maintenant=MAINTENANT)
    exits.update.assert_called_once()
    exit_id, company_id, donnees = exits.update.call_args.args
    assert (exit_id, company_id) == ("x1", "c1")
    note = donnees["exit_notes"][CLE_NOTE]
    assert note == {
        "timestamp": MAINTENANT.isoformat(),
        "periode": "09/2026",
        "generated_documents_to_review": ["attestation_pole_emploi", "solde_tout_compte"],
    }
    assert donnees["exit_notes"]["autre"] == {"garde": True}
    exits.list.assert_called_once_with("c1", employee_id="e1")


def test_rien_a_signaler_sans_document_genere_concerne():
    sortie = {"id": "x1", "status": "demission_effective", "last_working_day": "2026-09-15"}
    exits, docs = _depot([sortie], {"x1": [_doc("certificat_travail")]})
    signaler_bulletin_recalcule("e1", "c1", 2026, 9, exits=exits, documents=docs, maintenant=MAINTENANT)
    exits.update.assert_not_called()


def test_un_depart_annule_n_est_pas_signale():
    sortie = {"id": "x1", "status": "annulee", "last_working_day": "2026-09-15"}
    exits, docs = _depot([sortie], {"x1": [_doc("solde_tout_compte")]})
    signaler_bulletin_recalcule("e1", "c1", 2026, 9, exits=exits, documents=docs, maintenant=MAINTENANT)
    exits.update.assert_not_called()
    docs.list_by_exit.assert_not_called()
