"""Tests close_and_archive_exit (clôture manuelle d'un départ depuis l'UI)."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.employee_exits.application.commands import close_and_archive_exit
from app.modules.employee_exits.application.dto import EmployeeExitApplicationError
from app.modules.employee_exits.domain.rules import resolve_archive_path

pytestmark = pytest.mark.unit

COMPANY_ID = "co-1"
EXIT_ID = "exit-1"
USER_ID = "user-1"


def _archive_statuses(mock_update_exit_status):
    return [call.args[2] for call in mock_update_exit_status.call_args_list]


@patch("app.modules.employee_exits.application.commands.update_exit_status")
@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
def test_close_and_archive_rupture_conventionnelle(
    mock_exit_repo_cls, mock_update_exit_status
):
    exit_repo = MagicMock()
    mock_exit_repo_cls.return_value = exit_repo
    exit_repo.get_by_id.side_effect = [
        {"id": EXIT_ID, "status": "rupture_en_negociation", "exit_type": "rupture_conventionnelle"},
        {"id": EXIT_ID, "status": "archivee", "exit_type": "rupture_conventionnelle"},
    ]

    result = close_and_archive_exit(
        EXIT_ID, COMPANY_ID, USER_ID, supabase_client=MagicMock()
    )

    assert result["status"] == "archivee"
    # Passe par homologuée pour éviter le contrôle des 15 jours de rétractation.
    assert _archive_statuses(mock_update_exit_status) == [
        "rupture_validee",
        "rupture_homologuee",
        "rupture_effective",
        "archivee",
    ]


@patch("app.modules.employee_exits.application.commands.update_exit_status")
@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
def test_close_and_archive_demission_skips_preavis(
    mock_exit_repo_cls, mock_update_exit_status
):
    exit_repo = MagicMock()
    mock_exit_repo_cls.return_value = exit_repo
    exit_repo.get_by_id.side_effect = [
        {"id": EXIT_ID, "status": "demission_recue", "exit_type": "demission"},
        {"id": EXIT_ID, "status": "archivee", "exit_type": "demission"},
    ]

    close_and_archive_exit(EXIT_ID, COMPANY_ID, USER_ID, supabase_client=MagicMock())

    assert _archive_statuses(mock_update_exit_status) == [
        "demission_effective",
        "archivee",
    ]


@patch("app.modules.employee_exits.application.commands.update_exit_status")
@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
def test_close_and_archive_idempotent_when_already_archived(
    mock_exit_repo_cls, mock_update_exit_status
):
    exit_repo = MagicMock()
    mock_exit_repo_cls.return_value = exit_repo
    exit_repo.get_by_id.return_value = {
        "id": EXIT_ID,
        "status": "archivee",
        "exit_type": "demission",
    }

    result = close_and_archive_exit(
        EXIT_ID, COMPANY_ID, USER_ID, supabase_client=MagicMock()
    )

    assert result["status"] == "archivee"
    mock_update_exit_status.assert_not_called()


@patch("app.modules.employee_exits.application.commands.update_exit_status")
@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
def test_close_and_archive_rejects_cancelled(
    mock_exit_repo_cls, mock_update_exit_status
):
    exit_repo = MagicMock()
    mock_exit_repo_cls.return_value = exit_repo
    exit_repo.get_by_id.return_value = {
        "id": EXIT_ID,
        "status": "annulee",
        "exit_type": "demission",
    }

    with pytest.raises(EmployeeExitApplicationError) as exc:
        close_and_archive_exit(EXIT_ID, COMPANY_ID, USER_ID, supabase_client=MagicMock())

    assert exc.value.status_code == 400
    mock_update_exit_status.assert_not_called()


@patch("app.modules.employee_exits.application.commands.EmployeeExitRepository")
def test_close_and_archive_not_found(mock_exit_repo_cls):
    exit_repo = MagicMock()
    mock_exit_repo_cls.return_value = exit_repo
    exit_repo.get_by_id.return_value = None

    with pytest.raises(EmployeeExitApplicationError) as exc:
        close_and_archive_exit(EXIT_ID, COMPANY_ID, USER_ID, supabase_client=MagicMock())

    assert exc.value.status_code == 404


@pytest.mark.parametrize(
    "exit_type,current_status,expected",
    [
        (
            "rupture_conventionnelle",
            "rupture_en_negociation",
            ["rupture_validee", "rupture_homologuee", "rupture_effective", "archivee"],
        ),
        ("demission", "demission_recue", ["demission_effective", "archivee"]),
        ("demission", "demission_preavis_en_cours", ["demission_effective", "archivee"]),
        (
            "licenciement",
            "licenciement_convocation",
            ["licenciement_notifie", "licenciement_effective", "archivee"],
        ),
        (
            "licenciement",
            "licenciement_preavis_en_cours",
            ["licenciement_effective", "archivee"],
        ),
        ("depart_retraite", "demission_effective", ["archivee"]),
        ("demission", "archivee", []),
    ],
)
def test_resolve_archive_path(exit_type, current_status, expected):
    assert resolve_archive_path(exit_type, current_status) == expected
