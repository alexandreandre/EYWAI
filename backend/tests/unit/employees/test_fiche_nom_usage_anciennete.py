"""La fiche se modifie avec son nom d'usage et sa date d'ancienneté (retour du 10/11/2026).

Le nom d'usage était lu partout (bulletin, écrans, DSN S21.G00.30.003) mais le
schéma de mise à jour ne le connaissait pas : une saisie était perdue en silence.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.employees.schemas.requests import UpdateEmployee

pytestmark = pytest.mark.unit


def test_le_nom_d_usage_passe_a_la_mise_a_jour():
    donnees = UpdateEmployee(nom_usage="MARTIN").model_dump(exclude_unset=True)
    assert donnees == {"nom_usage": "MARTIN"}


def test_le_nom_d_usage_s_efface_par_null():
    donnees = UpdateEmployee(nom_usage=None).model_dump(exclude_unset=True)
    assert donnees == {"nom_usage": None}


def test_la_date_d_anciennete_passe_a_la_mise_a_jour():
    donnees = UpdateEmployee(seniority_reference_date="2019-03-01").model_dump(exclude_unset=True)
    assert donnees == {"seniority_reference_date": date(2019, 3, 1)}
