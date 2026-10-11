"""[H1] Un départ avec préavis se crée depuis l'écran.

La route transmet les dates en texte (« 2026-10-01 ») ; la création calculait
la fin du préavis par « texte + timedelta » : toute démission ou tout
licenciement avec des jours de préavis échouait (TypeError), d'où aucun
départ avec préavis en base au 11/10/2026.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.employee_exits.application import commands

pytestmark = pytest.mark.unit


def test_les_dates_du_preavis_se_calculent_sur_des_dates_recues_en_texte():
    with patch.object(
        commands,
        "get_employee_by_id",
        return_value={"company_id": "co", "employment_status": "actif", "first_name": "A", "last_name": "B"},
    ), patch.object(commands, "exit_block_reason", return_value=None), patch.object(
        commands, "EmployeeExitRepository"
    ) as depot, patch.object(commands, "update_employee_employment_status"), patch.object(
        commands, "create_default_checklist_sync"
    ), patch.object(commands, "_run_post_create_indemnities_and_docs"):
        depot.return_value.create.side_effect = lambda ligne: {**ligne, "id": "exit-1"}
        cree = commands.create_employee_exit(
            {
                "employee_id": "emp-1",
                "exit_type": "demission",
                "exit_request_date": "2026-10-01",
                "last_working_day": "2026-11-30",
                "notice_period_days": 60,
                "is_gross_misconduct": False,
                "notice_indemnity_type": "executed",
            },
            "co",
            "user-1",
            supabase_client=MagicMock(),
        )

    assert cree["notice_start_date"] == "2026-10-01"
    assert cree["notice_end_date"] == "2026-11-30"
