"""Isolation inter-entreprises du catalogue d'outils Copilot, sans DB réelle."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.modules.copilot.application.tool_service import execute_tool
from app.modules.copilot.domain.tools import ToolCall, ToolName


pytestmark = pytest.mark.integration

MBC = "company-mbc"
MAJI = "company-maji"


ROWS = {
    "employees": [
        {
            "id": "mbc-jean",
            "company_id": MBC,
            "first_name": "Jean",
            "last_name": "Dupont",
            "job_title": "Comptable MBC",
            "employment_status": "actif",
        },
        {
            "id": "maji-jean",
            "company_id": MAJI,
            "first_name": "Jean",
            "last_name": "Dupont",
            "job_title": "Directeur MAJI",
            "employment_status": "actif",
        },
    ],
    "absence_requests": [
        {
            "id": "absence-mbc",
            "company_id": MBC,
            "type": "conges_payes",
            "status": "validated",
            "selected_days": ["2026-07-20"],
        },
        {
            "id": "absence-maji",
            "company_id": MAJI,
            "type": "maladie",
            "status": "validated",
            "selected_days": ["2026-07-20", "2026-07-21"],
        },
    ],
    "shifts": [
        {
            "id": "shift-mbc",
            "company_id": MBC,
            "employee_id": "mbc-jean",
            "shift_date": "2026-07-20",
            "is_locked": True,
            "transverse_category": None,
        },
        {
            "id": "shift-maji",
            "company_id": MAJI,
            "employee_id": "maji-jean",
            "shift_date": "2026-07-20",
            "is_locked": True,
            "transverse_category": None,
        },
    ],
}


class InMemoryQuery:
    def __init__(self, rows):
        self.rows = list(rows)
        self.count_requested = False

    def select(self, *_args, **kwargs):
        self.count_requested = kwargs.get("count") == "exact"
        return self

    def eq(self, column, value):
        self.rows = [row for row in self.rows if row.get(column) == value]
        return self

    def gte(self, column, value):
        self.rows = [row for row in self.rows if row.get(column) >= value]
        return self

    def lte(self, column, value):
        self.rows = [row for row in self.rows if row.get(column) <= value]
        return self

    def execute(self):
        return SimpleNamespace(
            data=list(self.rows),
            count=len(self.rows) if self.count_requested else None,
        )


class InMemoryClient:
    def table(self, name):
        return InMemoryQuery(ROWS[name])


@pytest.fixture
def isolated_tools():
    analytics = SimpleNamespace(
        effectif_actif=1,
        age_moyen=40.0,
        anciennete_moyenne_annees=3.0,
        masse_salariale_brute_totale=3000.0,
        turnover=SimpleNamespace(
            taux_turnover_annuel=0.0,
            nb_departs_12_mois=0,
            nb_embauches_12_mois=1,
        ),
        absenteisme=SimpleNamespace(
            taux_global=1.0,
            taux_maladie=0.0,
            taux_at=0.0,
        ),
    )

    def payroll(*, company_id, period, team_ids):
        assert team_ids is None
        return {"company_scope": company_id, "period": period, "effectif_actif": 1}

    with (
        patch(
            "app.modules.copilot.infrastructure.secure_queries.get_supabase_client",
            return_value=InMemoryClient(),
        ),
        patch(
            "app.modules.copilot.infrastructure.secure_queries.get_payroll_analytics_summary",
            side_effect=payroll,
        ),
        patch(
            "app.modules.copilot.infrastructure.secure_queries.build_analytics_avances",
            side_effect=lambda company_id: (
                analytics
                if company_id == MBC
                else pytest.fail("Le service RH a reçu le mauvais company_id")
            ),
        ),
    ):
        yield


def test_homonymous_maji_employee_never_appears_for_mbc(isolated_tools):
    result = execute_tool(
        ToolCall(
            tool=ToolName.EMPLOYEE_SEARCH,
            arguments={"name": "Jean Dupont"},
        ),
        company_id=MBC,
    )

    assert result["count"] == 1
    assert result["employees"][0]["id"] == "mbc-jean"
    assert "maji-jean" not in str(result)
    assert "Directeur MAJI" not in str(result)


@pytest.mark.parametrize(
    ("tool", "arguments", "expected"),
    [
        (ToolName.EMPLOYEE_COUNT, {}, {"count": 1}),
        (
            ToolName.ABSENCE_SUMMARY,
            {},
            {
                "periode": "tout l'historique (aucune période demandée)",
                "total_demandes": 1,
                "salaries_concernes": 0,
                "salaries_absents_aujourdhui": 0,
                "by_status": {"validated": 1},
                "by_type": {"conges_payes": 1},
                "total_selected_days": 1,
            },
        ),
        (
            ToolName.PLANNING_SUMMARY,
            {"date_start": "2026-07-20", "date_end": "2026-07-20"},
            {
                "date_start": "2026-07-20",
                "date_end": "2026-07-20",
                "total_shifts": 1,
                "employees_scheduled": 1,
                "locked_shifts": 1,
            },
        ),
    ],
)
def test_direct_tools_only_aggregate_mbc_rows(
    isolated_tools, tool, arguments, expected
):
    assert execute_tool(
        ToolCall(tool=tool, arguments=arguments), company_id=MBC
    ) == expected


def test_delegated_tools_receive_only_server_company(isolated_tools):
    payroll = execute_tool(
        ToolCall(tool=ToolName.PAYROLL_SUMMARY, arguments={"period": "2026-07"}),
        company_id=MBC,
    )
    indicators = execute_tool(
        ToolCall(tool=ToolName.HR_INDICATORS, arguments={}),
        company_id=MBC,
    )

    assert payroll["company_scope"] == MBC
    assert indicators["effectif_actif"] == 1
    assert MAJI not in str(payroll)
    assert MAJI not in str(indicators)
