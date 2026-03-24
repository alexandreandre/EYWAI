"""
Tests unitaires du domaine absences : entités, value objects et règles métier.

Aucune dépendance DB ni HTTP. Couvre :
- AbsenceRequestEntity (domain/entities.py)
- AbsenceBalanceValue, CalendarDayValue (domain/value_objects.py)
- calculate_acquired_cp, calculate_acquired_rtt, requires_salary_certificate (domain/rules.py)
- Enums / types (AbsenceType, AbsenceStatus, SALARY_CERTIFICATE_ABSENCE_TYPES)
"""
from datetime import date, datetime

import pytest

from app.modules.absences.domain.entities import AbsenceRequestEntity
from app.modules.absences.domain.enums import (
    SALARY_CERTIFICATE_ABSENCE_TYPES,
)
from app.modules.absences.domain.rules import (
    calculate_acquired_cp,
    calculate_acquired_rtt,
    requires_salary_certificate,
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
        assert entity.comment is None
        assert entity.manager_id is None
        assert entity.attachment_url is None
        assert entity.filename is None
        assert entity.event_subtype is None
        assert entity.jours_payes is None
        assert entity.created_at is None

    def test_entity_creation_full(self):
        """Création avec tous les champs optionnels."""
        created = datetime(2025, 3, 1, 10, 0, 0)
        entity = AbsenceRequestEntity(
            id="req-2",
            employee_id="emp-2",
            company_id="comp-2",
            type="evenement_familial",
            selected_days=[date(2025, 7, 1), date(2025, 7, 2)],
            status="validated",
            comment="Mariage",
            manager_id="mgr-1",
            attachment_url="bucket/path.pdf",
            filename="justif.pdf",
            event_subtype="mariage_salarie",
            jours_payes=2,
            created_at=created,
        )
        assert entity.comment == "Mariage"
        assert entity.manager_id == "mgr-1"
        assert entity.attachment_url == "bucket/path.pdf"
        assert entity.filename == "justif.pdf"
        assert entity.event_subtype == "mariage_salarie"
        assert entity.jours_payes == 2
        assert entity.created_at == created

    def test_entity_company_id_optional(self):
        """company_id peut être None."""
        entity = AbsenceRequestEntity(
            id="req-3",
            employee_id="emp-3",
            company_id=None,
            type="rtt",
            selected_days=[date(2025, 8, 15)],
            status="pending",
        )
        assert entity.company_id is None


# --- Value objects ---


class TestAbsenceBalanceValue:
    """Tests du value object AbsenceBalanceValue."""

    def test_balance_float_remaining(self):
        """remaining peut être un float."""
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

    def test_balance_string_remaining_na(self):
        """remaining peut être une chaîne (ex. 'N/A', 'selon événement')."""
        balance = AbsenceBalanceValue(
            type="Congé sans solde",
            acquired=0,
            taken=2,
            remaining="N/A",
        )
        assert balance.remaining == "N/A"

    def test_balance_selon_evenement(self):
        """remaining 'selon événement' pour événement familial."""
        balance = AbsenceBalanceValue(
            type="Événement familial",
            acquired=0,
            taken=0,
            remaining="selon événement",
        )
        assert balance.remaining == "selon événement"


class TestCalendarDayValue:
    """Tests du value object CalendarDayValue."""

    def test_calendar_day_default_heures(self):
        """heures_prevues par défaut à 0.0."""
        day = CalendarDayValue(jour=15, type="travail")
        assert day.jour == 15
        assert day.type == "travail"
        assert day.heures_prevues == 0.0

    def test_calendar_day_with_heures(self):
        """heures_prevues peut être renseigné."""
        day = CalendarDayValue(
            jour=10,
            type="conge",
            heures_prevues=7.0,
        )
        assert day.heures_prevues == 7.0

    def test_calendar_day_types(self):
        """Types courants : travail, conge, rtt."""
        for t in ("travail", "conge", "rtt"):
            day = CalendarDayValue(jour=1, type=t)
            assert day.type == t


# --- Règles métier : calculate_acquired_cp ---


class TestCalculateAcquiredCp:
    """Règle : jours de CP acquis (période 1er juin N-1 → 31 mai N, 2.5 j/mois, arrondi supérieur)."""

    def test_hire_after_period_end_returns_zero(self):
        """Embauche après la fin de la période → 0 jour acquis."""
        # Période courante (today en sept 2025) : 1er juin 2024 → 31 mai 2025
        today = date(2025, 9, 1)
        hire_date = date(2025, 7, 1)  # après 31 mai 2025
        assert calculate_acquired_cp(hire_date, today) == 0.0

    def test_hire_at_period_start_full_year(self):
        """Embauche au 1er juin → 12 mois → 30 jours, plafonnés à 25 (2.5*10) en général ; ici 12*2.5=30 ceil=30."""
        today = date(2025, 6, 15)  # période 2024-06-01 → 2025-05-31
        hire_date = date(2024, 6, 1)
        acquired = calculate_acquired_cp(hire_date, today)
        assert acquired == 30.0  # 12 mois * 2.5 = 30

    def test_hire_mid_period_prorata(self):
        """Embauche en cours de période → prorata des mois travaillés."""
        today = date(2025, 6, 1)  # période 2024-06-01 → 2025-05-31
        hire_date = date(2024, 10, 1)  # 8 mois (oct, nov, déc, jan, fév, mar, avr, mai)
        acquired = calculate_acquired_cp(hire_date, today)
        # 8 * 2.5 = 20
        assert acquired == 20.0

    def test_hire_before_period_start_counts_from_period_start(self):
        """Embauche avant le début de la période : calcul à partir du 1er juin."""
        today = date(2025, 6, 1)  # période 2024-06-01 → 2025-05-31
        hire_date = date(2023, 1, 1)
        acquired = calculate_acquired_cp(hire_date, today)
        assert acquired == 30.0  # 12 mois complets

    def test_today_before_june_uses_previous_period(self):
        """Si today est avant juin, la période est N-2 juin → N-1 mai."""
        today = date(2025, 3, 1)  # période 2023-06-01 → 2024-05-31
        hire_date = date(2023, 6, 1)
        acquired = calculate_acquired_cp(hire_date, today)
        assert acquired == 30.0

    def test_partial_month_ceil(self):
        """Un mois partiel compte comme un mois (ceil)."""
        # today après juin → période 2024-06-01 → 2025-05-31
        today = date(2025, 6, 1)
        hire_date = date(2025, 5, 15)  # 1 mois (mai) dans la période
        acquired = calculate_acquired_cp(hire_date, today)
        assert acquired == 3.0  # ceil(2.5) = 3


# --- Règles métier : calculate_acquired_rtt ---


class TestCalculateAcquiredRtt:
    """Règle : RTT acquis pour l'année (prorata si embauche en cours d'année)."""

    def test_hire_previous_year_full_quota(self):
        """Embauche l'année précédente → quota annuel complet (défaut 10)."""
        today = date(2025, 6, 1)
        hire_date = date(2024, 1, 15)
        assert calculate_acquired_rtt(hire_date, today) == 10.0

    def test_hire_same_year_prorata(self):
        """Embauche en cours d'année → prorata (10/12 * mois restants)."""
        today = date(2025, 6, 1)
        hire_date = date(2025, 4, 1)  # avril, mai, juin = 3 mois
        acquired = calculate_acquired_rtt(hire_date, today)
        # (10/12) * 3 = 2.5
        assert acquired == 2.5

    def test_hire_july_same_year(self):
        """Embauche en juillet → 6 mois (juil à déc)."""
        today = date(2025, 12, 15)
        hire_date = date(2025, 7, 1)
        acquired = calculate_acquired_rtt(hire_date, today)
        # 10/12 * 6 = 5.0
        assert acquired == 5.0

    def test_custom_rtt_annual_base(self):
        """rtt_annual_base personnalisé."""
        today = date(2025, 6, 1)
        hire_date = date(2024, 1, 1)
        assert calculate_acquired_rtt(hire_date, today, rtt_annual_base=12.0) == 12.0


# --- Règles métier : requires_salary_certificate ---


class TestRequiresSalaryCertificate:
    """Règle : types d'absence nécessitant une attestation de salaire."""

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
        """Les types d'arrêt maladie/AT/maternité/paternité requièrent une attestation."""
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
        """Congés, RTT, sans solde, etc. ne requièrent pas d'attestation."""
        assert requires_salary_certificate(absence_type) is False

    def test_salary_certificate_types_constant_complete(self):
        """SALARY_CERTIFICATE_ABSENCE_TYPES contient exactement les 5 types attendus."""
        assert set(SALARY_CERTIFICATE_ABSENCE_TYPES) == {
            "arret_maladie",
            "arret_at",
            "arret_paternite",
            "arret_maternite",
            "arret_maladie_pro",
        }
