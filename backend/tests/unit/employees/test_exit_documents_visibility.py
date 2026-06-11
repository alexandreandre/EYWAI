"""Visibilité des documents de sortie côté employé."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.employees.infrastructure import queries as infra_queries

pytestmark = pytest.mark.unit


def _mock_table_chain(data=None, *, maybe_single=False):
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    if maybe_single:
        chain.maybe_single.return_value = chain
    chain.execute.return_value = MagicMock(data=data)
    return chain


@patch.object(infra_queries, "_storage_signed_urls")
@patch.object(infra_queries, "supabase")
def test_fetch_published_exit_documents_includes_procedure_docs_when_en_sortie(
    mock_supabase, mock_signed_urls
):
    """En cours de départ : les documents générés sont visibles sans publication RH."""
    mock_signed_urls.return_value = ("https://dl", "https://pv")

    employee_table = _mock_table_chain(
        {"employment_status": "en_sortie", "current_exit_id": "exit-1"},
        maybe_single=True,
    )
    published_table = _mock_table_chain([])
    exit_docs_table = _mock_table_chain(
        [
            {
                "id": "exit-doc-1",
                "document_type": "certificat_travail",
                "document_category": "generated",
                "storage_path": "exits/exit-1/certificat.pdf",
                "generated_at": "2026-06-01T10:00:00Z",
            }
        ]
    )

    def table_side_effect(name):
        if name == "employees":
            return employee_table
        if name == "employee_documents":
            return published_table
        if name == "exit_documents":
            return exit_docs_table
        raise AssertionError(f"table inattendue: {name}")

    mock_supabase.table.side_effect = table_side_effect

    result = infra_queries.fetch_published_exit_documents("emp-1", "company-1")

    assert len(result) == 1
    assert result[0]["id"] == "exit-doc-1"
    assert result[0]["name"] == "Certificat de travail"
    assert result[0]["url"] == "https://dl"
    assert result[0]["is_published"] is False


@patch.object(infra_queries, "_storage_signed_urls")
@patch.object(infra_queries, "supabase")
def test_fetch_published_exit_documents_skips_procedure_docs_when_actif(
    mock_supabase, mock_signed_urls
):
    """Hors départ : seuls les documents publiés sont retournés."""
    mock_signed_urls.return_value = ("https://dl", "https://pv")

    employee_table = _mock_table_chain(
        {"employment_status": "actif", "current_exit_id": None},
        maybe_single=True,
    )
    published_table = _mock_table_chain(
        [
            {
                "id": "pub-1",
                "document_name": "Certificat de travail",
                "storage_path": "employees/emp-1/certificat.pdf",
                "published_at": "2026-06-10T10:00:00Z",
                "document_type": "certificat_travail",
                "document_category": "autres",
            }
        ]
    )

    def table_side_effect(name):
        if name == "employees":
            return employee_table
        if name == "employee_documents":
            return published_table
        raise AssertionError(f"table inattendue: {name}")

    mock_supabase.table.side_effect = table_side_effect

    result = infra_queries.fetch_published_exit_documents("emp-1", "company-1")

    assert len(result) == 1
    assert result[0]["id"] == "pub-1"
    assert result[0]["is_published"] is True
    mock_supabase.table.assert_any_call("employee_documents")


@patch.object(infra_queries, "_storage_signed_urls")
@patch.object(infra_queries, "supabase")
def test_fetch_published_exit_documents_deduplicates_published_procedure_docs(
    mock_supabase, mock_signed_urls
):
    """Un document déjà publié n'apparaît pas une seconde fois via la procédure."""
    mock_signed_urls.return_value = ("https://dl", "https://pv")

    employee_table = _mock_table_chain(
        {"employment_status": "en_sortie", "current_exit_id": "exit-1"},
        maybe_single=True,
    )
    published_table = _mock_table_chain(
        [
            {
                "id": "pub-1",
                "document_name": "Certificat de travail",
                "storage_path": "employees/emp-1/certificat.pdf",
                "published_at": "2026-06-10T10:00:00Z",
                "document_type": "certificat_travail",
                "document_category": "autres",
                "source_exit_document_id": "exit-doc-1",
            }
        ]
    )
    exit_docs_table = _mock_table_chain(
        [
            {
                "id": "exit-doc-1",
                "document_type": "certificat_travail",
                "document_category": "generated",
                "storage_path": "exits/exit-1/certificat.pdf",
                "generated_at": "2026-06-01T10:00:00Z",
            }
        ]
    )

    def table_side_effect(name):
        if name == "employees":
            return employee_table
        if name == "employee_documents":
            return published_table
        if name == "exit_documents":
            return exit_docs_table
        raise AssertionError(f"table inattendue: {name}")

    mock_supabase.table.side_effect = table_side_effect

    result = infra_queries.fetch_published_exit_documents("emp-1", "company-1")

    assert len(result) == 1
    assert result[0]["id"] == "pub-1"
    assert result[0]["is_published"] is True
