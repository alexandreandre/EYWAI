"""IJ de maladie : un mois de référence sans bulletin vaut le salaire de la fiche.

C'est une estimation, que le décompte de la caisse remplace. Elle pouvait finir
sur le bulletin sans que rien ne le dise.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.maintien_salaire_service import alerte_ij_mois_sans_bulletin

pytestmark = pytest.mark.unit


def test_dit_combien_de_mois_sont_estimes():
    assert alerte_ij_mois_sans_bulletin({"salaires_bruts_reference": [2000.0, None, None]}, 40.0) == (
        "IJSS estimées : 2 mois de référence sans bulletin, salaire de la fiche retenu. "
        "Reportez le décompte de la CPAM dans Suivi IJSS."
    )


def test_un_mois_au_singulier():
    assert "1 mois de référence" in alerte_ij_mois_sans_bulletin(
        {"salaires_bruts_reference": [2000.0, 2000.0]}, 40.0
    )


def test_trois_bulletins_rien_a_dire():
    assert alerte_ij_mois_sans_bulletin({"salaires_bruts_reference": [1.0, 2.0, 3.0]}, 40.0) is None


def test_aperçu_sans_bruts_fournis_rien_a_dire():
    assert alerte_ij_mois_sans_bulletin({}, 40.0) is None


def test_aucune_ij_rien_a_dire():
    assert alerte_ij_mois_sans_bulletin({"salaires_bruts_reference": [None, None, None]}, 0.0) is None
