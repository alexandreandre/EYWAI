"""Tests unitaires — agrégation anomalies pré-paie."""

import calendar
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.modulation.domain.entities import ModulationSettings
from app.modules.payroll.application import preflight_anomalies
from app.shared.domain.periode_variables import FenetreVariables

_SERVICE = "app.modules.schedules.application.periode_a_saisir_service"


def _mois_civil(year: int, month: int) -> FenetreVariables:
    return FenetreVariables(
        debut=date(year, month, 1),
        fin=date(year, month, calendar.monthrange(year, month)[1]),
        origine="regle",
    )


@pytest.fixture(autouse=True)
def _periode_a_saisir_sur_le_mock_supabase():
    """La période à saisir (mois civil ∪ fenêtre) lit les plannings via son
    propre dépôt : on le fait lire les lignes que `_configure_supabase` a posées
    sur le mock du module, fenêtre = mois civil sauf si un test la remplace."""

    def _lignes(ids, year, month):
        rows = (
            preflight_anomalies.supabase.table("employee_schedules")
            .select("employee_id, planned_calendar, actual_hours")
            .eq("company_id", "")
            .eq("year", year)
            .eq("month", month)
            .in_("employee_id", ids)
            .execute()
            .data
            or []
        )
        return {str(r["employee_id"]): r for r in rows}

    with patch(f"{_SERVICE}.schedule_repository") as mock_repo, patch(
        f"{_SERVICE}.resoudre_fenetre_variables",
        side_effect=lambda cid, y, m, societe=None: _mois_civil(y, m),
    ), patch(
        "app.modules.payroll.application.preflight_anomalies.resoudre_fenetre_variables",
        side_effect=lambda cid, y, m, societe=None: _mois_civil(y, m),
    ), patch(
        "app.modules.payroll.application.preflight_anomalies.bulletins_sur_une_autre_fenetre",
        return_value=[],
    ):
        mock_repo.list_schedules_for_employees.side_effect = _lignes
        yield

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


def _default_mod_settings(**overrides) -> ModulationSettings:
    return ModulationSettings(**overrides)


class TestBuildPreflightAnomalies:
    @patch(
        "app.modules.schedules.infrastructure.punch_accounting_repository.list_overtime_reviews",
        return_value=[],
    )
    @patch("app.modules.modulation.infrastructure.repository.get_modulation_settings")
    @patch("app.modules.payroll.application.preflight_anomalies.badgeuse_service.get_company_period_summary")
    @patch("app.modules.payroll.application.preflight_anomalies.preflight_repository.list_resolutions")
    @patch("app.modules.payroll.application.preflight_anomalies.supabase")
    def test_ecart_heures_detected(
        self, mock_supabase, mock_resolutions, mock_badgeuse, mock_mod_settings, _mock_punch_reviews
    ):
        mock_mod_settings.return_value = _default_mod_settings()
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

    @patch(
        "app.modules.schedules.infrastructure.punch_accounting_repository.list_overtime_reviews",
        return_value=[],
    )
    @patch("app.modules.modulation.infrastructure.repository.get_modulation_settings")
    @patch("app.modules.payroll.application.preflight_anomalies.badgeuse_service.get_company_period_summary")
    @patch("app.modules.payroll.application.preflight_anomalies.preflight_repository.list_resolutions")
    @patch("app.modules.payroll.application.preflight_anomalies.supabase")
    def test_merge_justification(
        self, mock_supabase, mock_resolutions, mock_badgeuse, mock_mod_settings, _mock_punch_reviews
    ):
        mock_mod_settings.return_value = _default_mod_settings()
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

    @patch(
        "app.modules.schedules.infrastructure.punch_accounting_repository.list_overtime_reviews",
        return_value=[],
    )
    @patch(
        "app.modules.modulation.application.overtime_routing_queries.list_overtime_routing"
    )
    @patch("app.modules.modulation.infrastructure.repository.get_modulation_settings")
    @patch("app.modules.payroll.application.preflight_anomalies.badgeuse_service.get_company_period_summary")
    @patch("app.modules.payroll.application.preflight_anomalies.preflight_repository.list_resolutions")
    @patch("app.modules.payroll.application.preflight_anomalies.supabase")
    def test_hs_routing_pending_when_manual_policy(
        self,
        mock_supabase,
        mock_resolutions,
        mock_badgeuse,
        mock_mod_settings,
        mock_list_routing,
        _mock_punch_reviews,
    ):
        _configure_supabase(mock_supabase, schedules=[])
        mock_resolutions.return_value = []
        mock_badgeuse.return_value = {}
        mock_mod_settings.return_value = _default_mod_settings(hs_routing_policy="manual")
        mock_list_routing.return_value = [
            {
                "employee_id": EMP_ID,
                "employee_name": "Jean Dupont",
                "total_hs_hours": 4.5,
                "status": "pending",
            }
        ]

        with patch(
            "app.modules.absences.infrastructure.repository.absence_repository.list_validated_for_employees",
            return_value=[],
        ):
            result = preflight_anomalies.build_preflight_anomalies(COMPANY_ID, 2026, 6)

        routing = next(a for a in result.anomalies if a.type == "hs_routing_pending")
        assert routing.severity == "bloquant"
        assert routing.status == "a_traiter"
        assert "4.5" in routing.message

    @patch(
        "app.modules.schedules.infrastructure.punch_accounting_repository.list_overtime_reviews",
        return_value=[],
    )
    @patch(
        "app.modules.modulation.application.overtime_routing_queries.list_overtime_routing"
    )
    @patch("app.modules.modulation.infrastructure.repository.get_modulation_settings")
    @patch("app.modules.payroll.application.preflight_anomalies.badgeuse_service.get_company_period_summary")
    @patch("app.modules.payroll.application.preflight_anomalies.preflight_repository.list_resolutions")
    @patch("app.modules.payroll.application.preflight_anomalies.supabase")
    def test_hs_routing_skipped_when_not_manual(
        self,
        mock_supabase,
        mock_resolutions,
        mock_badgeuse,
        mock_mod_settings,
        mock_list_routing,
        _mock_punch_reviews,
    ):
        _configure_supabase(mock_supabase, schedules=[])
        mock_resolutions.return_value = []
        mock_badgeuse.return_value = {}
        mock_mod_settings.return_value = _default_mod_settings(hs_routing_policy="account_all")

        with patch(
            "app.modules.absences.infrastructure.repository.absence_repository.list_validated_for_employees",
            return_value=[],
        ):
            result = preflight_anomalies.build_preflight_anomalies(COMPANY_ID, 2026, 6)

        mock_list_routing.assert_not_called()
        assert "hs_routing_pending" not in [a.type for a in result.anomalies]


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


class TestPeriodeASaisir:
    """L'anomalie « heures non saisies » juge la fenêtre des variables, pas le mois civil."""

    @patch(
        "app.modules.schedules.infrastructure.punch_accounting_repository.list_overtime_reviews",
        return_value=[],
    )
    @patch("app.modules.modulation.infrastructure.repository.get_modulation_settings")
    @patch("app.modules.payroll.application.preflight_anomalies.badgeuse_service.get_company_period_summary")
    @patch("app.modules.payroll.application.preflight_anomalies.preflight_repository.list_resolutions")
    @patch("app.modules.payroll.application.preflight_anomalies.supabase")
    def test_des_jours_hors_fenetre_ne_font_pas_d_anomalie(
        self, mock_supabase, mock_resolutions, mock_badgeuse, mock_mod_settings, _mock_punch
    ):
        mock_mod_settings.return_value = _default_mod_settings()
        mock_resolutions.return_value = []
        mock_badgeuse.return_value = {}
        actual = [d for d in _full_june_2026_actual() if d["jour"] <= 19]  # S26 (22–26/06) non saisie
        _configure_supabase(
            mock_supabase,
            schedules=[
                {
                    "employee_id": EMP_ID,
                    "planned_calendar": {"calendrier_prevu": _full_june_2026_planned()},
                    "actual_hours": {"calendrier_reel": actual},
                }
            ],
        )

        # Fenêtre arrêtée au 21/06 (début au 1er pour ne pas dépendre d'une ligne de mai).
        with patch(
            f"{_SERVICE}.resoudre_fenetre_variables",
            return_value=FenetreVariables(debut=date(2026, 6, 1), fin=date(2026, 6, 21), origine="regle"),
        ), patch(
            "app.modules.absences.infrastructure.repository.absence_repository.list_validated_for_employees",
            return_value=[],
        ):
            result = preflight_anomalies.build_preflight_anomalies(COMPANY_ID, 2026, 6)

        # Les 22–26/06 et 29–30/06 sont hors fenêtre : informatifs, pas d'anomalie.
        assert [a for a in result.anomalies if a.type == "heures_non_saisies"] == []

    @patch(
        "app.modules.schedules.infrastructure.punch_accounting_repository.list_overtime_reviews",
        return_value=[],
    )
    @patch("app.modules.modulation.infrastructure.repository.get_modulation_settings")
    @patch("app.modules.payroll.application.preflight_anomalies.badgeuse_service.get_company_period_summary")
    @patch("app.modules.payroll.application.preflight_anomalies.preflight_repository.list_resolutions")
    @patch("app.modules.payroll.application.preflight_anomalies.supabase")
    def test_un_jour_de_la_fenetre_manquant_fait_une_anomalie_datee(
        self, mock_supabase, mock_resolutions, mock_badgeuse, mock_mod_settings, _mock_punch
    ):
        mock_mod_settings.return_value = _default_mod_settings()
        mock_resolutions.return_value = []
        mock_badgeuse.return_value = {}
        actual = [d for d in _full_june_2026_actual() if d["jour"] != 15]
        _configure_supabase(
            mock_supabase,
            schedules=[
                {
                    "employee_id": EMP_ID,
                    "planned_calendar": {"calendrier_prevu": _full_june_2026_planned()},
                    "actual_hours": {"calendrier_reel": actual},
                }
            ],
        )

        with patch(
            "app.modules.absences.infrastructure.repository.absence_repository.list_validated_for_employees",
            return_value=[],
        ):
            result = preflight_anomalies.build_preflight_anomalies(COMPANY_ID, 2026, 6)

        anomalie = next(a for a in result.anomalies if a.type == "heures_non_saisies")
        assert anomalie.jours_manquants == ["2026-06-15"]
        assert anomalie.fenetre["debut"] == "2026-06-01"
        assert "15/06" in anomalie.message

    @patch("app.modules.payroll.application.preflight_anomalies.bulletins_sur_une_autre_fenetre")
    @patch(
        "app.modules.schedules.infrastructure.punch_accounting_repository.list_overtime_reviews",
        return_value=[],
    )
    @patch("app.modules.modulation.infrastructure.repository.get_modulation_settings")
    @patch("app.modules.payroll.application.preflight_anomalies.badgeuse_service.get_company_period_summary")
    @patch("app.modules.payroll.application.preflight_anomalies.preflight_repository.list_resolutions")
    @patch("app.modules.payroll.application.preflight_anomalies.supabase")
    def test_un_bulletin_calcule_sur_une_autre_fenetre_est_a_regenerer(
        self, mock_supabase, mock_resolutions, mock_badgeuse, mock_mod_settings, _mock_punch, mock_bulletins
    ):
        mock_mod_settings.return_value = _default_mod_settings()
        mock_resolutions.return_value = []
        mock_badgeuse.return_value = {}
        _configure_supabase(
            mock_supabase,
            schedules=[
                {
                    "employee_id": EMP_ID,
                    "planned_calendar": {"calendrier_prevu": _full_june_2026_planned()},
                    "actual_hours": {"calendrier_reel": _full_june_2026_actual()},
                }
            ],
        )
        mock_bulletins.return_value = [
            {"employee_id": EMP_ID, "status": "brouillon", "debut": "2026-06-01", "fin": "2026-06-21"}
        ]

        with patch(
            "app.modules.absences.infrastructure.repository.absence_repository.list_validated_for_employees",
            return_value=[],
        ):
            result = preflight_anomalies.build_preflight_anomalies(COMPANY_ID, 2026, 6)

        anomalie = next(a for a in result.anomalies if a.type == "fenetre_modifiee")
        assert anomalie.severity == "a_verifier"
        assert "01/06 → 21/06" in anomalie.message and "01/06 → 30/06" in anomalie.message
        assert anomalie.fenetre["fin"] == "2026-06-30"
        assert result.counts.fenetre_modifiee == 1
