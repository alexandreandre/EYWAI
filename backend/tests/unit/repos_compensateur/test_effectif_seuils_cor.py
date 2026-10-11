"""Le taux de la contrepartie en repos suit l'effectif saisi pour l'année,
pas le nombre de comptes de la société (enquête du 10/10/2026)."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.repos_compensateur.infrastructure import queries

pytestmark = pytest.mark.unit


def _supabase(ligne):
    client = MagicMock()
    (
        client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value
    ) = MagicMock(data=ligne)
    return client


def test_l_effectif_saisi_pour_l_annee_l_emporte_sur_les_comptes():
    ligne = {"effectif": 25, "settings": {"effectif_seuils": {"2026": 16}}}
    with patch.object(queries, "supabase", _supabase(ligne)) as client:
        assert queries.get_company_effectif("societe", 2026) == 16
    client.table.return_value.select.assert_called_once_with("effectif, settings")


def test_sans_saisie_le_nombre_de_comptes_reste_le_dernier_recours():
    with patch.object(queries, "supabase", _supabase({"effectif": 25, "settings": {}})):
        assert queries.get_company_effectif("societe", 2026) == 25


def test_societe_introuvable():
    with patch.object(queries, "supabase", _supabase(None)):
        assert queries.get_company_effectif("societe", 2026) is None
