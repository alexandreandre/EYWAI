"""
Lecture des salariés à exporter.

Le test central est celui du cloisonnement : le serveur ne fait jamais confiance
aux identifiants reçus du navigateur. Sans le filtre sur `company_id`, une requête
modifiée exporterait les salariés d'une autre société.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.residence_permits.infrastructure.queries import (
    fetch_employees_for_residence_permits_export,
)

pytestmark = pytest.mark.unit

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def table():
    """Client Supabase simulé : chaque filtre renvoie le même objet chaînable."""
    with patch(
        "app.modules.residence_permits.infrastructure.queries._get_client"
    ) as get_client:
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.in_.return_value = chain
        chain.execute.return_value = MagicMock(data=[{"id": "emp-1"}])
        client = MagicMock()
        client.table.return_value = chain
        get_client.return_value = client
        yield chain


def test_borne_sur_l_entreprise_active(table):
    """Garde-fou central : le cloisonnement entre sociétés."""
    fetch_employees_for_residence_permits_export(COMPANY_ID, ["emp-1"])

    assert ("company_id", COMPANY_ID) in [c.args for c in table.eq.call_args_list]


def test_reprend_les_bornes_de_la_route_liste(table):
    """Mêmes filtres que la liste : soumis au titre, et en emploi."""
    fetch_employees_for_residence_permits_export(COMPANY_ID, ["emp-1"])

    assert ("is_subject_to_residence_permit", True) in [
        c.args for c in table.eq.call_args_list
    ]
    assert ("employment_status", ["actif", "en_sortie"]) in [
        c.args for c in table.in_.call_args_list
    ]


def test_filtre_sur_les_identifiants_demandes(table):
    fetch_employees_for_residence_permits_export(COMPANY_ID, ["emp-1", "emp-2"])

    assert ("id", ["emp-1", "emp-2"]) in [c.args for c in table.in_.call_args_list]


def test_liste_vide_ne_declenche_aucune_requete(table):
    """Sans identifiant, `IN ()` ramènerait toute l'entreprise : on ne requête pas."""
    assert fetch_employees_for_residence_permits_export(COMPANY_ID, []) == []
    table.execute.assert_not_called()


def test_colonnes_enrichies_demandees(table):
    fetch_employees_for_residence_permits_export(COMPANY_ID, ["emp-1"])

    colonnes = table.select.call_args.args[0]
    for attendue in ("matricule", "job_title", "hire_date", "nationalite"):
        assert attendue in colonnes


def test_retourne_une_liste_vide_si_aucune_donnee(table):
    table.execute.return_value = MagicMock(data=None)

    assert fetch_employees_for_residence_permits_export(COMPANY_ID, ["emp-1"]) == []
