"""L'écran « Saisies du mois » ne montre pas les régularisations : elles se gèrent depuis le bulletin."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.monthly_inputs.application import queries

pytestmark = pytest.mark.unit

ORDINAIRE = {"id": "s1", "name": "Prime", "amount": 50, "correction_ligne": None}
REGUL = {
    "id": "s2",
    "name": "Régularisation",
    "amount": 0,
    "correction_ligne": {"type": "regularisation_cotisation"},
}


def test_la_liste_d_un_salarie_ecarte_les_regularisations():
    with patch.object(queries.monthly_inputs_repository, "list_by_employee_period", return_value=[ORDINAIRE, REGUL]):
        resultat = queries.list_monthly_inputs_by_employee_period("e", 2026, 10, "c")
    assert [s["id"] for s in resultat.items] == ["s1"]


def test_la_liste_de_la_societe_ecarte_les_regularisations():
    with patch.object(queries.monthly_inputs_repository, "list_by_period", return_value=[ORDINAIRE, REGUL]):
        resultat = queries.list_monthly_inputs_by_period(2026, 10, "c")
    assert [s["id"] for s in resultat.items] == ["s1"]
