"""L'éditeur du certificat de travail montre l'adresse et la ville que le PDF imprime.

Tournage H.4, scène 9 (20/10/2026, relevé le 12/10, D6) : « Adresse » et
« Ville » restaient vides dans « Édition - Certificat de travail » alors que le
PDF imprimait l'adresse. Les données éditables lisaient `address` et `city` sur
la société, qui porte `adresse_rue`, `adresse_code_postal`, `adresse_ville` ;
le PDF, lui, les lit par `get_company_address` et `get_company_city`.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.employee_exits.application import queries
from app.shared.infrastructure.pdf.helpers import get_company_address, get_company_city

pytestmark = pytest.mark.unit

SOCIETE = {
    "id": "co-1",
    "company_name": "Société QA",
    "siret": "53438649500053",
    "adresse_rue": "12 rue des Lilas",
    "adresse_code_postal": "38280",
    "adresse_ville": "Villette d'Anthon",
}


def _details(document):
    doc_repo, exit_repo = MagicMock(), MagicMock()
    doc_repo.get_by_id.return_value = document
    exit_repo.get_by_id.return_value = {"id": "exit-1", "employee_id": "e1", "exit_type": "fin_cdd"}
    with (
        patch.object(queries, "ExitDocumentRepository", return_value=doc_repo),
        patch.object(queries, "EmployeeExitRepository", return_value=exit_repo),
        patch.object(queries, "get_exit_storage_provider", return_value=MagicMock()),
        patch.object(queries, "get_employee_full", return_value={"first_name": "Jeanne"}),
        patch.object(queries, "get_company_by_id", return_value=dict(SOCIETE)),
    ):
        return queries.get_exit_document_details("exit-1", "doc-1", "co-1", supabase_client=MagicMock())


def _certificat(**modifs):
    return {
        "id": "doc-1",
        "exit_id": "exit-1",
        "company_id": "co-1",
        "document_type": "certificat_travail",
        "document_category": "generated",
        "storage_path": None,
        "generation_data": None,
        **modifs,
    }


def test_un_certificat_jamais_edite_montre_l_adresse_et_la_ville_du_pdf():
    societe = _details(_certificat())["document_data"]["company"]
    assert societe["address"] == "12 rue des Lilas, 38280 Villette d'Anthon"
    assert societe["address"] == get_company_address(SOCIETE)
    assert societe["city"] == "Villette d'Anthon" == get_company_city(SOCIETE)


def test_un_certificat_deja_edite_sans_adresse_la_montre_aussi():
    edite = {"company": {"name": "Société QA", "address": "", "city": ""}, "employee": {}, "exit": {}}
    societe = _details(_certificat(generation_data=edite))["document_data"]["company"]
    assert societe["address"] == "12 rue des Lilas, 38280 Villette d'Anthon"
    assert societe["city"] == "Villette d'Anthon"


def test_une_adresse_saisie_a_l_editeur_reste_celle_de_la_gestionnaire():
    edite = {"company": {"address": "3 place du Marché, 69000 Lyon", "city": "Lyon"}, "employee": {}, "exit": {}}
    societe = _details(_certificat(generation_data=edite))["document_data"]["company"]
    assert societe["address"] == "3 place du Marché, 69000 Lyon"
    assert societe["city"] == "Lyon"
