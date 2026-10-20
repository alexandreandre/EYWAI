"""Publier un document de sortie pour la première fois ne plante plus (relevé du tournage H.4, 20/10/2026).

Avec maybe_single(), postgrest renvoie None (et non une réponse vide) quand aucune
ligne ne correspond. La recherche du document déjà publié lisait r.data sur None :
« 'NoneType' object has no attribute 'data' », et aucun document de départ n'a
jamais pu être publié. Même lecture dans les trois autres requêtes du module.
"""

from unittest.mock import MagicMock

import pytest

from app.modules.employee_exits.infrastructure import queries

pytestmark = pytest.mark.unit


def _client_sans_ligne():
    sb = MagicMock()
    chaine = sb.table.return_value
    for methode in ("select", "eq"):
        getattr(chaine, methode).return_value = chaine
    chaine.maybe_single.return_value = chaine
    chaine.execute.return_value = None
    return sb


def test_un_document_jamais_publie_se_lit_comme_absent():
    assert queries.get_employee_document_by_source_exit_document("emp", "doc", _client_sans_ligne()) is None


@pytest.mark.parametrize(
    "lecture",
    [queries.get_employee_by_id, queries.get_employee_full, queries.get_company_by_id],
)
def test_une_ligne_absente_se_lit_comme_absente(lecture):
    assert lecture("inconnu", _client_sans_ligne()) is None
