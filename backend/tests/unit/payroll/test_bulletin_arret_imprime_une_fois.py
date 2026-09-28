"""Les retenues d'arrêt s'impriment une fois sur le bulletin."""

import pytest

from app.modules.payroll.documents.bulletin_view import construire_lignes

pytestmark = pytest.mark.unit

ARRET = {
    "libelle": "Absence arrêt maladie du 17/08 au 31/08",
    "quantite": 77.0,
    "taux": 13.143,
    "gain": None,
    "perte": 1012.01,
    "is_arret_maladie": True,
}


def test_une_retenue_d_arret_n_apparait_qu_une_fois():
    lignes = construire_lignes(
        {
            "details_absences": [ARRET],
            "details_maintien": [ARRET],
            "salaire_brut": 1162.72,
        }
    )
    assert sum(1 for l in lignes if "arrêt maladie" in str(l.get("libelle"))) == 1
