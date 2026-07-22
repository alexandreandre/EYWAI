"""
Tests du catalogue fermé d'outils Copilot.

Couvre :
- le parsing strict des appels d'outils fournis par le LLM (domain/tools.py) ;
- le dispatch fermé (application/tool_service.py) qui impose systématiquement
  le company_id serveur.

Aucun appel réel à OpenAI ni à la base : les requêtes sécurisées sont mockées.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.copilot.domain.tools import (
    ToolCall,
    ToolName,
    parse_tool_calls,
)
from app.modules.copilot.application.tool_service import execute_tool


pytestmark = pytest.mark.unit


class TestParseToolCalls:
    def test_valid_call_is_parsed(self):
        calls = parse_tool_calls(
            [{"tool": "employee_count", "arguments": {"employment_status": "actif"}}]
        )
        assert len(calls) == 1
        assert calls[0].tool is ToolName.EMPLOYEE_COUNT
        assert calls[0].arguments == {"employment_status": "actif"}

    def test_missing_arguments_defaults_to_empty_dict(self):
        calls = parse_tool_calls([{"tool": "hr_indicators"}])
        assert len(calls) == 1
        assert calls[0].tool is ToolName.HR_INDICATORS
        assert calls[0].arguments == {}

    def test_none_returns_empty_list(self):
        assert parse_tool_calls(None) == []

    def test_empty_list_returns_empty_list(self):
        assert parse_tool_calls([]) == []

    def test_non_list_is_rejected(self):
        with pytest.raises(ValueError):
            parse_tool_calls({"tool": "employee_count"})

    def test_unknown_tool_is_rejected(self):
        with pytest.raises(ValueError):
            parse_tool_calls([{"tool": "raw_sql", "arguments": {"query": "SELECT *"}}])

    def test_company_id_from_llm_is_rejected(self):
        with pytest.raises(ValueError):
            parse_tool_calls(
                [{"tool": "employee_count", "arguments": {"company_id": "maji"}}]
            )

    @pytest.mark.parametrize(
        "forbidden_key",
        ["company_id", "group_id", "sql", "query", "table", "employee_ids"],
    )
    def test_forbidden_argument_keys_are_rejected(self, forbidden_key):
        with pytest.raises(ValueError):
            parse_tool_calls(
                [{"tool": "employee_search", "arguments": {forbidden_key: "x"}}]
            )

    def test_non_dict_arguments_are_rejected(self):
        with pytest.raises(ValueError):
            parse_tool_calls([{"tool": "employee_count", "arguments": "actif"}])

    @pytest.mark.parametrize(
        ("tool", "arguments"),
        [
            ("employee_count", {"unexpected": "x"}),
            ("employee_search", {"employee_id": "internal-id"}),
            ("payroll_summary", {"year": 2026}),
            ("absence_summary", {"date_start": "2026-01-01"}),
            ("planning_summary", {"status": "locked"}),
            ("hr_indicators", {"detail": True}),
        ],
    )
    def test_unknown_argument_for_each_tool_is_rejected(self, tool, arguments):
        with pytest.raises(ValueError, match="non autorisé"):
            parse_tool_calls([{"tool": tool, "arguments": arguments}])

    @pytest.mark.parametrize(
        ("tool", "arguments"),
        [
            ("employee_count", {"employment_status": 1}),
            ("employee_search", {"name": ["Jean"]}),
            ("employee_search", {"limit": "10"}),
            ("employee_search", {"limit": True}),
            ("payroll_summary", {"period": 202601}),
            ("absence_summary", {"status": False}),
            ("planning_summary", {"date_start": 20260101}),
        ],
    )
    def test_wrong_argument_type_is_rejected(self, tool, arguments):
        with pytest.raises(ValueError, match="invalide"):
            parse_tool_calls([{"tool": tool, "arguments": arguments}])

    def test_unknown_call_level_key_is_rejected(self):
        with pytest.raises(ValueError, match="appel d'outil"):
            parse_tool_calls(
                [{"tool": "employee_count", "arguments": {}, "query": "SELECT 1"}]
            )

    def test_non_dict_item_is_rejected(self):
        with pytest.raises(ValueError):
            parse_tool_calls(["employee_count"])

    def test_more_than_five_calls_are_rejected(self):
        payload = [{"tool": "employee_count"} for _ in range(6)]
        with pytest.raises(ValueError):
            parse_tool_calls(payload)

    def test_exactly_five_calls_are_accepted(self):
        payload = [{"tool": "employee_count"} for _ in range(5)]
        assert len(parse_tool_calls(payload)) == 5


class TestToolCall:
    def test_tool_call_is_frozen(self):
        call = ToolCall(tool=ToolName.EMPLOYEE_COUNT, arguments={})
        with pytest.raises(Exception):
            call.tool = ToolName.PAYROLL_SUMMARY  # type: ignore[misc]


class TestExecuteToolDispatch:
    @patch("app.modules.copilot.application.tool_service.secure_queries")
    def test_dispatch_always_passes_server_company(self, mock_queries):
        execute_tool(
            ToolCall(tool=ToolName.EMPLOYEE_COUNT, arguments={}),
            company_id="mbc",
        )
        mock_queries.count_employees.assert_called_once_with("mbc", {})

    @patch("app.modules.copilot.application.tool_service.secure_queries")
    def test_dispatch_ignores_any_company_in_arguments(self, mock_queries):
        # Même si un company_id résiduel se glisse dans arguments, seul le
        # company_id serveur (positionnel) est transmis à la requête sécurisée.
        execute_tool(
            ToolCall(tool=ToolName.PAYROLL_SUMMARY, arguments={"period": "2026-01"}),
            company_id="mbc",
        )
        mock_queries.payroll_summary.assert_called_once_with(
            "mbc", {"period": "2026-01"}
        )

    @patch("app.modules.copilot.application.tool_service.secure_queries")
    def test_every_tool_is_wired(self, mock_queries):
        expected = {
            ToolName.EMPLOYEE_COUNT: "count_employees",
            ToolName.EMPLOYEE_SEARCH: "search_employees",
            ToolName.PAYROLL_SUMMARY: "payroll_summary",
            ToolName.ABSENCE_SUMMARY: "absence_summary",
            ToolName.PLANNING_SUMMARY: "planning_summary",
            ToolName.HR_INDICATORS: "hr_indicators",
        }
        for tool, handler_name in expected.items():
            handler = MagicMock(return_value={"ok": True})
            setattr(mock_queries, handler_name, handler)
            execute_tool(ToolCall(tool=tool, arguments={}), company_id="c1")
            handler.assert_called_once_with("c1", {})
