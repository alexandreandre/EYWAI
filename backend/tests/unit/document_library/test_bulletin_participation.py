"""Tests unitaires — types document bulletin participation."""

from __future__ import annotations

from app.modules.document_library.schemas.requests import (
    CLIENT_TEMPLATE_ONLY_TYPES,
    DOCUMENT_TYPE_LABELS,
    KNOWN_DOCUMENT_TYPES,
)


def test_bulletin_types_in_catalog():
    assert "bulletin_participation" in KNOWN_DOCUMENT_TYPES
    assert "bulletin_interessement" in KNOWN_DOCUMENT_TYPES
    assert DOCUMENT_TYPE_LABELS["bulletin_participation"]
    assert DOCUMENT_TYPE_LABELS["bulletin_interessement"]


def test_bulletin_types_client_only():
    assert "bulletin_participation" in CLIENT_TEMPLATE_ONLY_TYPES
    assert "bulletin_interessement" in CLIENT_TEMPLATE_ONLY_TYPES


def test_participation_variables_in_catalog():
    from app.services.document_variables import list_document_variables

    keys = {v["key"] for v in list_document_variables()}
    assert "montant_brut" in keys
    assert "net_a_payer_final" in keys
    assert "clause_defaut_15j" in keys
