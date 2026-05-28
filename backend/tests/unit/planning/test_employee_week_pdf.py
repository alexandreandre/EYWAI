"""Export PDF et résolution employé — planning collaborateur."""

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.planning.application.employee_week_pdf import (
    generate_employee_week_planning_pdf,
)
from app.modules.planning.application import queries as planning_queries


def test_generate_employee_week_planning_pdf_returns_pdf_bytes():
    planning = {
        "week_start": date(2026, 5, 25),
        "week_end": date(2026, 5, 31),
        "status": "published",
        "shifts": [
            {
                "shift_date": date(2026, 5, 26),
                "start_time": "09:00:00",
                "end_time": "17:00:00",
                "shift_type": {"label": "Journée"},
                "location": "Site A",
            }
        ],
    }
    pdf = generate_employee_week_planning_pdf(planning)
    assert pdf.startswith(b"%PDF")


@patch(
    "app.modules.planning.application.queries.get_employee_planning",
    return_value={
        "week_start": date(2026, 5, 25),
        "week_end": date(2026, 5, 31),
        "status": "published",
        "team_view_enabled": False,
        "shifts": [],
        "employee_hours": [],
    },
)
@patch(
    "app.modules.planning.application.queries.resolve_employee_id_for_user_account",
    return_value="emp-resolved",
)
@patch("app.modules.planning.application.queries.planning_repository")
def test_get_my_planning_week_includes_employee_id(
    mock_repo, _mock_resolve, _mock_planning
):
    mock_repo.get_week_status.return_value = {"team_view_enabled": False}
    result = planning_queries.get_my_planning_week("auth-1", "co-1", "2026-05-25")
    assert result["employee_id"] == "emp-resolved"


@patch(
    "app.modules.planning.application.queries.get_my_planning_week",
    return_value={"status": "draft", "shifts": []},
)
def test_build_pdf_raises_when_week_is_draft(_mock_week):
    with pytest.raises(ValueError, match="pas encore publié"):
        planning_queries.build_my_planning_week_pdf("auth-1", "co-1", "2026-05-25")
