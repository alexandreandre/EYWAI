"""Tests unitaires — fiche de poste et bibliothèque."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.document_library.application import queries
from app.modules.document_library.schemas.requests import CLIENT_TEMPLATE_ONLY_TYPES
from app.services.document_variables import build_variables, get_unknown_variables, list_document_variables


def test_get_missing_types_excludes_client_only_types():
    with patch(
        "app.modules.document_library.application.queries.document_library_repository"
    ) as repo:
        repo.get_all.return_value = []
        missing = queries.get_missing_types("co-1")
    for t in CLIENT_TEMPLATE_ONLY_TYPES:
        assert t not in missing


def test_list_document_variables_has_flat_keys():
    keys = {v["key"] for v in list_document_variables()}
    assert "nom" in keys
    assert "prenom" in keys
    assert "missions" in keys
    assert "nom_entreprise" in keys


def test_build_variables_merges_custom_fields():
    vars_map = build_variables(
        {"first_name": "Marie", "last_name": "Dupont"},
        {"company_name": "ACME"},
        {"custom_fields": {"missions": "Vente B2B", "manager": "Jean"}},
    )
    assert vars_map["missions"] == "Vente B2B"
    assert vars_map["manager"] == "Jean"
    assert vars_map["prenom"] == "Marie"


def test_get_unknown_variables_detects_inconnu():
    known = {v["key"]: "" for v in list_document_variables()}
    unknown = get_unknown_variables("Poste : {{poste}} — {{inconnu}}", known)
    assert "inconnu" in unknown
    assert "poste" not in unknown


@patch.object(
    __import__("app.services.document_service", fromlist=["DocumentService"]).DocumentService,
    "get_active_template",
    return_value=None,
)
def test_generate_fiche_poste_without_template_raises(_mock_tpl):
    from app.services.document_service import DocumentService

    svc = DocumentService()
    with pytest.raises(ValueError, match="fiche de poste"):
        svc.generate_document(
            company_id="co-1",
            employee_id="emp-1",
            document_type="fiche_poste",
            category="attestation_courante",
            employee_data={"first_name": "A", "last_name": "B"},
            company_data={"company_name": "ACME"},
            persist=False,
        )
