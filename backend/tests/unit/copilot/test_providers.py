"""
Tests des helpers purs de providers.py (injection company_id, nettoyage SQL).

Fonctions pures : pas d'appel LLM ni DB.
"""

import pytest

from app.modules.copilot.infrastructure.providers import (
    _clean_generated_sql,
    _company_scope_hint,
    _inject_runtime_context,
)


pytestmark = pytest.mark.unit


class TestInjectRuntimeContext:
    def test_replaces_company_id_placeholder(self):
        schema = "WHERE employees.company_id = '<company_id>'"
        result = _inject_runtime_context(schema, "company-abc")
        assert "<company_id>" not in result
        assert "company-abc" in result

    def test_keeps_placeholder_when_no_company(self):
        schema = "WHERE employees.company_id = '<company_id>'"
        result = _inject_runtime_context(schema, None)
        assert "<company_id>" in result

    def test_replaces_today_token(self):
        result = _inject_runtime_context("date = {today}", None)
        assert "{today}" not in result


class TestCompanyScopeHint:
    def test_empty_when_no_company(self):
        assert _company_scope_hint(None) == ""

    def test_contains_company_id_and_instruction(self):
        hint = _company_scope_hint("company-xyz")
        assert "company-xyz" in hint
        assert "company_id" in hint


class TestCleanGeneratedSql:
    def test_strips_code_fence_and_semicolon(self):
        raw = "```sql\nSELECT 1;\n```"
        assert _clean_generated_sql(raw) == "SELECT 1"

    def test_replaces_leftover_placeholder_with_company_id(self):
        raw = "SELECT * FROM employees WHERE company_id = '<company_id>'"
        result = _clean_generated_sql(raw, "company-123")
        assert "<company_id>" not in result
        assert "company-123" in result

    def test_leaves_sql_untouched_without_company(self):
        raw = "SELECT * FROM employees WHERE company_id = '<company_id>'"
        result = _clean_generated_sql(raw, None)
        assert "<company_id>" in result
