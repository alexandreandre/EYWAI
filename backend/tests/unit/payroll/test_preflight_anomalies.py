"""Tests unitaires — agrégation anomalies pré-paie."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.payroll.application import preflight_anomalies

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
EMP_ID = "660e8400-e29b-41d4-a716-446655440001"


def _full_june_2026_planned(base_hours: float = 8.0, *, day1_hours: float | None = None):
    rows = []
    for day in range(1, 31):
        from datetime import date

        dt = date(2026, 6, day)
        if dt.weekday() >= 5:
            rows.append({"jour": day, "type": "weekend", "heures_prevues": 0})
            continue
        hours = day1_hours if day == 1 and day1_hours is not None else base_hours
        rows.append({"jour": day, "type": "travail", "heures_prevues": hours})
    return rows


def _full_june_2026_actual(base_hours: float = 8.0, *, day1_hours: float | None = None):
    planned = _full_june_2026_planned(base_hours, day1_hours=day1_hours)
    actual = []
    for row in planned:
        if row["type"] == "weekend":
            actual.append({"jour": row["jour"], "type": "weekend", "heures_faites": 0})
            continue
        hours = (
            day1_hours
            if row["jour"] == 1 and day1_hours is not None
            else base_hours
        )
        actual.append({"jour": row["jour"], "type": "travail", "heures_faites": hours})
    return actual


def _employee():
    return {
        "id": EMP_ID,
        "first_name": "Jean",
        "last_name": "Dupont",
        "statut": "ouvrier",
        "team_id": None,
    }


def _configure_supabase(mock_supabase, *, schedules=None, resolutions=None):
    employees_execute = MagicMock(data=[_employee()])
    schedules_execute = MagicMock(data=schedules or [])
    resolutions_execute = MagicMock(data=resolutions or [])

    employees_chain = MagicMock()
    employees_chain.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
        employees_execute
    )

    schedules_chain = MagicMock()
    schedules_chain.select.return_value.eq.return_value.eq.return_value.eq.return_value.in_.return_value.execute.return_value = (
        schedules_execute
    )

    resolutions_chain = MagicMock()
    resolutions_chain.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = (
        resolutions_execute
    )

    def table(name):
        if name == "employees":
            return employees_chain
        if name == "employee_schedules":
            return schedules_chain
        if name == "payroll_anomaly_resolutions":
            return resolutions_chain
        raise AssertionError(f"unexpected table {name}")

    mock_supabase.table.side_effect = table


class TestBuildPreflightAnomalies:
    @patch("app.modules.payroll.application.preflight_anomalies.badgeuse_service.get_company_period_summary")
    @patch("app.modules.payroll.application.preflight_anomalies.preflight_repository.list_resolutions")
    @patch("app.modules.payroll.application.preflight_anomalies.supabase")
    def test_ecart_heures_detected(self, mock_supabase, mock_resolutions, mock_badgeuse):
        _configure_supabase(
            mock_supabase,
            schedules=[
                {
                    "employee_id": EMP_ID,
                    "planned_calendar": {"calendrier_prevu": _full_june_2026_planned()},
                    "actual_hours": {
                        "calendrier_reel": _full_june_2026_actual(day1_hours=28)
                    },
                }
            ],
        )
        mock_resolutions.return_value = []
        mock_badgeuse.return_value = {}

        with patch(
            "app.modules.absences.infrastructure.repository.absence_repository.list_validated_for_employees",
            return_value=[],
        ):
            result = preflight_anomalies.build_preflight_anomalies(COMPANY_ID, 2026, 6)

        types = [a.type for a in result.anomalies]
        assert "ecart_heures" in types
        ecart = next(a for a in result.anomalies if a.type == "ecart_heures")
        assert ecart.severity == "bloquant"
        assert ecart.status == "a_traiter"
        assert result.total_open >= 1

    @patch("app.modules.payroll.application.preflight_anomalies.badgeuse_service.get_company_period_summary")
    @patch("app.modules.payroll.application.preflight_anomalies.preflight_repository.list_resolutions")
    @patch("app.modules.payroll.application.preflight_anomalies.supabase")
    def test_merge_justification(self, mock_supabase, mock_resolutions, mock_badgeuse):
        _configure_supabase(
            mock_supabase,
            schedules=[
                {
                    "employee_id": EMP_ID,
                    "planned_calendar": {"calendrier_prevu": _full_june_2026_planned()},
                    "actual_hours": {
                        "calendrier_reel": _full_june_2026_actual(day1_hours=28)
                    },
                }
            ],
        )
        mock_resolutions.return_value = [
            {
                "employee_id": EMP_ID,
                "anomaly_type": "ecart_heures",
                "status": "justifie",
                "motif": "directeur_site",
                "commentaire": "OK directeur",
                "resolved_by": "user-1",
                "resolved_at": "2026-06-01T10:00:00+00:00",
            }
        ]
        mock_badgeuse.return_value = {}

        with patch(
            "app.modules.absences.infrastructure.repository.absence_repository.list_validated_for_employees",
            return_value=[],
        ):
            result = preflight_anomalies.build_preflight_anomalies(COMPANY_ID, 2026, 6)

        ecart = next(a for a in result.anomalies if a.type == "ecart_heures")
        assert ecart.status == "justifie"
        assert ecart.resolution is not None
        assert ecart.resolution.motif == "directeur_site"
        assert result.total_open == 0


class TestJustifyAnomaly:
    @patch("app.modules.payroll.application.preflight_anomalies.preflight_repository.upsert_resolution")
    def test_autre_requires_comment(self, mock_upsert):
        with pytest.raises(ValueError, match="commentaire"):
            preflight_anomalies.justify_anomaly(
                company_id=COMPANY_ID,
                employee_id=EMP_ID,
                year=2026,
                month=6,
                anomaly_type="ecart_heures",
                motif="autre",
                commentaire="",
                resolved_by="user-1",
            )
        mock_upsert.assert_not_called()

    @patch("app.modules.payroll.application.preflight_anomalies.preflight_repository.upsert_resolution")
    def test_directeur_site_ok(self, mock_upsert):
        mock_upsert.return_value = {"status": "justifie"}
        row = preflight_anomalies.justify_anomaly(
            company_id=COMPANY_ID,
            employee_id=EMP_ID,
            year=2026,
            month=6,
            anomaly_type="ecart_heures",
            motif="directeur_site",
            commentaire=None,
            resolved_by="user-1",
        )
        assert row["status"] == "justifie"
        mock_upsert.assert_called_once()
