"""
Tests unitaires du domaine absences : entités, value objects et règles métier.

Aucune dépendance DB ni HTTP. Couvre :
- AbsenceRequestEntity (domain/entities.py)
- AbsenceBalanceValue, CalendarDayValue (domain/value_objects.py)
- calculate_acquired_cp, calculate_acquired_rtt, requires_salary_certificate (domain/rules.py)
- Enums / types (AbsenceType, AbsenceStatus, SALARY_CERTIFICATE_ABSENCE_TYPES)
"""

from datetime import date, datetime, timedelta

import pytest

from app.modules.absences.domain.cp_seniority import EmployeeCpSeniorityContext
from app.modules.absences.domain.entities import AbsenceRequestEntity
from app.modules.absences.domain.enums import (
    SALARY_CERTIFICATE_ABSENCE_TYPES,
)
from app.modules.absences.domain.leave_policy import (
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
)
from app.modules.absences.domain.rules import (
    calculate_acquired_cp,
    calculate_acquired_cp_for_period,
    calculate_acquired_rtt,
    calculate_rtt_annual_calendar,
    compute_absence_balances,
    compute_cp_balances_for_bulletin,
    compute_cp_period_balances,
    count_absence_days_taken,
    get_available_conge_paye_days,
    get_cp_previous_reference_period,
    get_cp_reference_period,
    get_rtt_year_end_status,
    requires_salary_certificate,
    resolve_rtt_annual_base,
)
from app.modules.absences.domain.value_objects import (
    AbsenceBalanceValue,
    CalendarDayValue,
)


# --- Entités ---


class TestAbsenceRequestEntity:
    """Tests de l'entité AbsenceRequestEntity."""

    def test_entity_creation_minimal(self):
        """Création avec champs obligatoires uniquement."""
        entity = AbsenceRequestEntity(
            id="req-1",
            employee_id="emp-1",
            company_id="comp-1",
            type="conge_paye",
            selected_days=[date(2025, 6, 10)],
            status="pending",
        )
        assert entity.id == "req-1"
        assert entity.employee_id == "emp-1"
        assert entity.company_id == "comp-1"
        assert entity.type == "conge_paye"
        assert entity.selected_days == [date(2025, 6, 10)]
        assert entity.status == "pending"

    def test_entity_with_optional_fields(self):
        """Création avec champs optionnels."""
        entity = AbsenceRequestEntity(
            id="req-2",
            employee_id="emp-2",
            company_id="comp-2",
            type="rtt",
            selected_days=[date(2025, 7, 1), date(2025, 7, 2)],
            status="validated",
            comment="Vacances",
            attachment_url="path/to/file.pdf",
            created_at=datetime(2025, 6, 1, 10, 0, 0),
        )
        assert entity.comment == "Vacances"
        assert entity.attachment_url == "path/to/file.pdf"
        assert entity.created_at is not None


# --- Value Objects ---


class TestAbsenceBalanceValue:
    """Tests du value object AbsenceBalanceValue."""

    def test_balance_creation(self):
        balance = AbsenceBalanceValue(
            type="Congés Payés",
            acquired=25.0,
            taken=5.0,
            remaining=20.0,
        )
        assert balance.type == "Congés Payés"
        assert balance.acquired == 25.0
        assert balance.taken == 5.0
        assert balance.remaining == 20.0


class TestCalendarDayValue:
    """Tests du value object CalendarDayValue."""

    def test_calendar_day_creation(self):
        day = CalendarDayValue(jour=15, type="conge", heures_prevues=7.0)
        assert day.jour == 15
        assert day.type == "conge"
        assert day.heures_prevues == 7.0


# --- Règles métier : périodes CP ---


class TestCpReferencePeriod:
    def test_janvier_periode_en_cours(self):
        assert get_cp_reference_period(date(2026, 1, 31)) == (
            date(2025, 6, 1),
            date(2026, 5, 31),
        )

    def test_septembre_periode_en_cours(self):
        assert get_cp_reference_period(date(2026, 9, 15)) == (
            date(2026, 6, 1),
            date(2027, 5, 31),
        )

    def test_periode_precedente(self):
        assert get_cp_previous_reference_period(date(2026, 1, 31)) == (
            date(2024, 6, 1),
            date(2025, 5, 31),
        )


# --- Règles métier : calculate_acquired_cp ---


class TestCalculateAcquiredCp:
    """Règle L3141-3 : 2,5 j/mois sur la période en cours, cumulé jusqu'à ref_date."""

    def test_hire_after_ref_date_returns_zero(self):
        ref = date(2026, 1, 31)
        hire_date = date(2026, 3, 1)
        assert calculate_acquired_cp(hire_date, ref) == 0.0

    def test_debut_periode_un_mois(self):
        """Bulletin de juin : 1 mois acquis sur la nouvelle période."""
        ref = date(2025, 6, 15)
        hire_date = date(2020, 1, 1)
        assert calculate_acquired_cp(hire_date, ref) == 3.0

    def test_fin_annee_civile_dans_periode(self):
        """31/12/2025 → 7 mois (juin–déc) = 17,5 → 18 jours."""
        ref = date(2025, 12, 31)
        hire_date = date(2020, 1, 1)
        assert calculate_acquired_cp(hire_date, ref) == 18.0

    def test_janvier_dix_mois_depuis_juin(self):
        """31/01/2026 → 8 mois (juin–jan) = 20 jours."""
        ref = date(2026, 1, 31)
        hire_date = date(2020, 1, 1)
        assert calculate_acquired_cp(hire_date, ref) == 20.0

    def test_prorata_embauche_en_cours_de_periode(self):
        ref = date(2026, 1, 31)
        hire_date = date(2025, 10, 1)
        assert calculate_acquired_cp(hire_date, ref) == 10.0  # oct–jan = 4 * 2.5

    def test_periode_complete_cloturee(self):
        prev_start, prev_end = get_cp_previous_reference_period(date(2026, 1, 31))
        hire_date = date(2020, 1, 1)
        assert calculate_acquired_cp_for_period(hire_date, prev_start, prev_end) == 30.0


# --- Règles métier : calculate_acquired_rtt ---


class TestCalculateAcquiredRtt:
    """Règle : RTT acquis pour l'année (prorata si embauche en cours d'année)."""

    def test_hire_previous_year_full_quota(self):
        today = date(2025, 6, 1)
        hire_date = date(2024, 1, 15)
        assert calculate_acquired_rtt(hire_date, today) == 10.0

    def test_hire_same_year_prorata(self):
        today = date(2025, 6, 1)
        hire_date = date(2025, 4, 1)
        acquired = calculate_acquired_rtt(hire_date, today)
        assert acquired == 2.5

    def test_hire_july_same_year(self):
        today = date(2025, 12, 15)
        hire_date = date(2025, 7, 1)
        acquired = calculate_acquired_rtt(hire_date, today)
        assert acquired == 5.0

    def test_custom_rtt_annual_base(self):
        today = date(2025, 6, 1)
        hire_date = date(2024, 1, 1)
        assert calculate_acquired_rtt(hire_date, today, rtt_annual_base=12.0) == 12.0


# --- Règles métier : requires_salary_certificate ---


class TestRequiresSalaryCertificate:
    @pytest.mark.parametrize(
        "absence_type",
        [
            "arret_maladie",
            "arret_at",
            "arret_paternite",
            "arret_maternite",
            "arret_maladie_pro",
        ],
    )
    def test_returns_true_for_certificate_types(self, absence_type: str):
        assert requires_salary_certificate(absence_type) is True

    @pytest.mark.parametrize(
        "absence_type",
        [
            "conge_paye",
            "rtt",
            "sans_solde",
            "repos_compensateur",
            "evenement_familial",
        ],
    )
    def test_returns_false_for_non_certificate_types(self, absence_type: str):
        assert requires_salary_certificate(absence_type) is False

    def test_salary_certificate_types_constant_complete(self):
        assert set(SALARY_CERTIFICATE_ABSENCE_TYPES) == {
            "arret_maladie",
            "arret_at",
            "arret_paternite",
            "arret_maternite",
            "arret_maladie_pro",
        }


class TestCountAbsenceDaysTaken:
    def test_filtre_jours_apres_date_reference(self):
        ref = date(2026, 1, 31)
        requests = [
            {
                "type": "conge_paye",
                "selected_days": ["2026-01-10", "2026-02-05"],
                "jours_payes": 2,
            }
        ]
        assert count_absence_days_taken(requests, "conge_paye", ref) == 1.0

    def test_filtre_periode_reference(self):
        ref = date(2026, 1, 31)
        requests = [
            {
                "type": "conge_paye",
                "selected_days": ["2025-08-10", "2026-01-10"],
                "jours_payes": 2,
            }
        ]
        current_start, current_end = get_cp_reference_period(ref)
        assert (
            count_absence_days_taken(
                requests,
                "conge_paye",
                ref,
                period_start=current_start,
                period_end=current_end,
            )
            == 2.0
        )

    def test_jours_payes_limite_cp_sur_demande_partielle(self):
        ref = date(2026, 3, 31)
        requests = [
            {
                "type": "conge_paye",
                "selected_days": ["2026-03-10", "2026-03-11", "2026-03-12"],
                "jours_payes": 2,
            }
        ]
        assert count_absence_days_taken(requests, "conge_paye", ref) == 2.0


class TestComputeAbsenceBalances:
    def test_solde_cp_coherent(self):
        hire_date = date(2020, 1, 1)
        ref = date(2026, 6, 30)
        requests = [
            {
                "type": "conge_paye",
                "selected_days": ["2026-06-05", "2026-06-10"],
                "jours_payes": 2,
            }
        ]
        balances = compute_absence_balances(hire_date, requests, ref)
        cp = balances["conges_payes"]
        assert cp["acquis"] == calculate_acquired_cp(hire_date, ref)
        assert cp["pris"] == 2.0
        assert cp["solde"] == pytest.approx(cp["acquis"] - 2.0)


class TestComputeCpBalancesForBulletin:
    def test_double_ligne_n_et_n_moins_un(self):
        hire_date = date(2020, 1, 1)
        ref = date(2026, 1, 31)
        requests = [
            {
                "type": "conge_paye",
                "selected_days": ["2025-07-01", "2025-07-02", "2025-07-03"],
                "jours_payes": 3,
            },
            {
                "type": "conge_paye",
                "selected_days": ["2026-01-06"],
                "jours_payes": 1,
            },
        ]
        result = compute_cp_balances_for_bulletin(hire_date, requests, ref)
        assert result["periode_courante"]["acquis"] == 20.0
        assert result["periode_courante"]["pris"] == 4.0
        assert result["periode_courante"]["solde"] == 16.0
        assert result["periode_precedente"]["acquis"] == 30.0
        assert result["periode_precedente"]["pris"] == 0.0
        assert result["periode_precedente"]["solde"] == 30.0


class TestCongePayeAvailability:
    def test_pending_requests_reduce_available_balance(self):
        hire_date = date(2020, 1, 1)
        ref = date(2026, 3, 1)
        requests = [
            {
                "type": "conge_paye",
                "status": "pending",
                "selected_days": ["2026-03-10", "2026-03-11"],
            },
        ]
        from app.modules.absences.domain.rules import (
            calculate_acquired_cp,
            get_available_conge_paye_days,
            validate_conge_paye_request_days,
        )

        acquis = calculate_acquired_cp(hire_date, ref)
        available = get_available_conge_paye_days(hire_date, requests, ref)
        assert available == acquis - 2

        validate_conge_paye_request_days(
            hire_date, requests, [date(2026, 3, 12)], ref_date=ref
        )

        remaining = int(acquis - 2)
        start = date(2026, 3, 12)
        too_many_days = [start + timedelta(days=i) for i in range(remaining + 1)]
        with pytest.raises(ValueError, match="insuffisant"):
            validate_conge_paye_request_days(
                hire_date,
                requests,
                too_many_days,
                ref_date=ref,
            )


class TestCpCarryover:
    def test_carryover_disabled_matches_legacy_single_period(self):
        hire_date = date(2020, 1, 1)
        ref = date(2026, 3, 1)
        policy = LeavePolicySettings(cp_carryover_enabled=False)
        balances = compute_absence_balances(hire_date, [], ref, policy=policy)
        assert balances["conges_payes"]["acquis"] == calculate_acquired_cp(
            hire_date, ref, policy=policy
        )

    def test_carryover_n1_consumed_before_n(self):
        hire_date = date(2020, 1, 1)
        ref = date(2026, 1, 31)
        policy = LeavePolicySettings(cp_carryover_enabled=True)
        prev_start, prev_end = get_cp_previous_reference_period(ref)
        prev_acquis = calculate_acquired_cp_for_period(
            hire_date, prev_start, prev_end, policy=policy
        )
        adjustment = EmployeeLeaveAdjustment(
            cp_n1_opening_balance=5.0 - prev_acquis
        )
        requests = [
            {
                "type": "conge_paye",
                "selected_days": ["2026-01-06", "2026-01-07"],
                "jours_payes": 2,
            },
        ]
        periods = compute_cp_period_balances(
            hire_date, requests, ref, policy=policy, adjustment=adjustment
        )
        assert periods["n1_remaining"] == 3.0

    def test_available_includes_n1_when_carryover_enabled(self):
        hire_date = date(2020, 1, 1)
        ref = date(2026, 1, 31)
        policy = LeavePolicySettings(cp_carryover_enabled=True)
        prev_start, prev_end = get_cp_previous_reference_period(ref)
        prev_acquis = calculate_acquired_cp_for_period(
            hire_date, prev_start, prev_end, policy=policy
        )
        adjustment = EmployeeLeaveAdjustment(
            cp_n1_opening_balance=4.0 - prev_acquis
        )
        available = get_available_conge_paye_days(
            hire_date, [], ref, policy=policy, adjustment=adjustment
        )
        assert available >= 4.0


class TestRttPolicy:
    def test_calendar_formula_leap_year(self):
        assert calculate_rtt_annual_calendar(2024) == 11.0
        assert calculate_rtt_annual_calendar(2025) == 10.0

    def test_resolve_custom_annual_days(self):
        policy = LeavePolicySettings(rtt_annual_days=12.0)
        assert resolve_rtt_annual_base(2025, policy) == 12.0

    def test_rtt_forfeiture_zeros_remaining(self):
        hire_date = date(2020, 1, 1)
        ref_year = 2025
        policy = LeavePolicySettings()
        adjustment = EmployeeLeaveAdjustment(
            rtt_forfeited_days=3.0, rtt_forfeited_at="2025-12-31T00:00:00Z"
        )
        status = get_rtt_year_end_status(
            hire_date, [], ref_year, policy=policy, adjustment=adjustment
        )
        assert status["already_closed"] is True

    def test_year_end_status_requires_forfait_context_when_cadres_only(self):
        hire_date = date(2020, 1, 1)
        ref_year = 2026
        policy = LeavePolicySettings(
            rtt_use_forfait_jours_formula=True,
            rtt_forfait_cadres_only=True,
        )
        forfait_ctx = EmployeeCpSeniorityContext(
            hire_date=hire_date,
            statut="Cadre forfait jour",
        )
        non_forfait_ctx = EmployeeCpSeniorityContext(
            hire_date=hire_date,
            statut="Employé",
        )

        without_ctx = get_rtt_year_end_status(
            hire_date, [], ref_year, policy=policy
        )
        with_forfait = get_rtt_year_end_status(
            hire_date, [], ref_year, policy=policy, employee_ctx=forfait_ctx
        )
        with_non_forfait = get_rtt_year_end_status(
            hire_date, [], ref_year, policy=policy, employee_ctx=non_forfait_ctx
        )

        assert without_ctx["remaining"] == 0.0
        assert with_non_forfait["remaining"] == 0.0
        assert with_forfait["remaining"] > 0.0
        assert with_forfait["closure_required"] is True
