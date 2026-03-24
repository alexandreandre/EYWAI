"""
Tests du domain du module copilot : règles métier, enums.

Sans DB, sans HTTP. Couvre les règles (only_select_allowed) et les enums (MessageRole).
Les entités et value_objects sont des placeholders vides, donc non testés.
"""
import pytest

from app.modules.copilot.domain.rules import only_select_allowed
from app.modules.copilot.domain.enums import MessageRole


pytestmark = pytest.mark.unit


class TestOnlySelectAllowed:
    """Règle métier : seule une requête SQL SELECT est autorisée."""

    def test_select_simple_returns_true(self):
        assert only_select_allowed("SELECT * FROM employees") is True

    def test_select_lowercase_returns_true(self):
        assert only_select_allowed("select id, first_name from employees") is True

    def test_select_with_whitespace_returns_true(self):
        assert only_select_allowed("   \n  SELECT * FROM payslips  ") is True

    def test_select_with_comments_or_multiline_returns_true(self):
        assert only_select_allowed("SELECT 1") is True
        assert only_select_allowed("SELECT id FROM employees WHERE company_id = 'x'") is True

    def test_insert_returns_false(self):
        assert only_select_allowed("INSERT INTO employees (id) VALUES ('x')") is False

    def test_update_returns_false(self):
        assert only_select_allowed("UPDATE employees SET first_name = 'X'") is False

    def test_delete_returns_false(self):
        assert only_select_allowed("DELETE FROM employees") is False

    def test_drop_returns_false(self):
        assert only_select_allowed("DROP TABLE employees") is False

    def test_empty_or_none_returns_false(self):
        assert only_select_allowed("") is False
        assert only_select_allowed(None) is False

    def test_whitespace_only_returns_false(self):
        assert only_select_allowed("   \n\t  ") is False

    def test_non_select_sql_returns_false(self):
        assert only_select_allowed("WITH x AS (SELECT 1) INSERT INTO t SELECT * FROM x") is False


class TestMessageRole:
    """Enum des rôles de message (aligné OpenAI)."""

    def test_user_value(self):
        assert MessageRole.USER == "user"

    def test_assistant_value(self):
        assert MessageRole.ASSISTANT == "assistant"

    def test_system_value(self):
        assert MessageRole.SYSTEM == "system"

    def test_all_members_exist(self):
        assert set(MessageRole) == {MessageRole.USER, MessageRole.ASSISTANT, MessageRole.SYSTEM}

    def test_string_usage(self):
        """Les valeurs sont des str, utilisables directement dans l'API."""
        assert isinstance(MessageRole.USER.value, str)
        assert MessageRole.USER.value == "user"
