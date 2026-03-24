"""
Tests unitaires du domaine schedules : entités, value objects, règles métier et enums.

Aucune dépendance DB ni HTTP. Couvre :
- EmployeeScheduleMonth (domain/entities.py)
- Periode, CalendrierJour (domain/value_objects.py)
- is_forfait_jour, normalize_planned_calendar_for_forfait_jour, normalize_actual_hours_for_forfait_jour (domain/rules.py)
- DayType (domain/enums.py)
- ScheduleNotFoundError, ScheduleValidationError, ScheduleDatabaseError (domain/exceptions.py)
"""
import pytest

from app.modules.schedules.domain.entities import EmployeeScheduleMonth
from app.modules.schedules.domain.enums import DayType
from app.modules.schedules.domain.exceptions import (
    ScheduleDatabaseError,
    ScheduleNotFoundError,
    ScheduleValidationError,
)
from app.modules.schedules.domain.rules import (
    is_forfait_jour,
    normalize_actual_hours_for_forfait_jour,
    normalize_planned_calendar_for_forfait_jour,
)
from app.modules.schedules.domain.value_objects import CalendrierJour, Periode


# --- Entités ---


class TestEmployeeScheduleMonth:
    """Tests de l'entité EmployeeScheduleMonth."""

    def test_entity_creation_minimal(self):
        """Création avec champs obligatoires uniquement."""
        entity = EmployeeScheduleMonth(
            employee_id="emp-1",
            company_id="comp-1",
            year=2025,
            month=3,
        )
        assert entity.employee_id == "emp-1"
        assert entity.company_id == "comp-1"
        assert entity.year == 2025
        assert entity.month == 3
        assert entity.planned_calendar is None
        assert entity.actual_hours is None
        assert entity.payroll_events is None
        assert entity.cumuls is None

    def test_entity_creation_with_calendars(self):
        """Création avec calendriers et cumuls."""
        planned = {"calendrier_prevu": [{"jour": 1, "type": "work", "heures_prevues": 8}]}
        actual = {"calendrier_reel": [{"jour": 1, "heures_faites": 7.5}]}
        cumuls = {"heures_remunerees": 160}
        entity = EmployeeScheduleMonth(
            employee_id="emp-2",
            company_id="comp-2",
            year=2025,
            month=6,
            planned_calendar=planned,
            actual_hours=actual,
            payroll_events={},
            cumuls=cumuls,
        )
        assert entity.planned_calendar == planned
        assert entity.actual_hours == actual
        assert entity.cumuls == cumuls

    def test_to_storage_returns_dict(self):
        """to_storage() retourne un dict (placeholder)."""
        entity = EmployeeScheduleMonth(
            employee_id="emp-1",
            company_id="comp-1",
            year=2025,
            month=3,
        )
        result = entity.to_storage()
        assert isinstance(result, dict)


# --- Value objects ---


class TestPeriode:
    """Tests du value object Periode."""

    def test_periode_creation(self):
        """Période (année, mois)."""
        p = Periode(year=2025, month=3)
        assert p.year == 2025
        assert p.month == 3


class TestCalendrierJour:
    """Tests du value object CalendrierJour."""

    def test_calendrier_jour_minimal(self):
        """Jour avec type uniquement."""
        c = CalendrierJour(jour=15, type="work")
        assert c.jour == 15
        assert c.type == "work"
        assert c.heures_prevues is None
        assert c.heures_faites is None

    def test_calendrier_jour_with_hours(self):
        """Jour avec heures prévues et faites."""
        c = CalendrierJour(
            jour=1,
            type="travail",
            heures_prevues=8.0,
            heures_faites=7.5,
        )
        assert c.heures_prevues == 8.0
        assert c.heures_faites == 7.5


# --- Règles métier ---


class TestIsForfaitJour:
    """Tests de la règle is_forfait_jour."""

    def test_statut_none_returns_false(self):
        """Statut None → False."""
        assert is_forfait_jour(None) is False

    def test_statut_empty_returns_false(self):
        """Statut vide → False."""
        assert is_forfait_jour("") is False

    def test_statut_forfait_jour_lowercase_returns_true(self):
        """Statut contenant 'forfait jour' en minuscules → True."""
        assert is_forfait_jour("cadre forfait jour") is True

    def test_statut_forfait_jour_mixed_case_returns_true(self):
        """Statut contenant 'Forfait Jour' → True (lower)."""
        assert is_forfait_jour("Cadre Forfait Jour") is True

    def test_statut_sans_forfait_jour_returns_false(self):
        """Statut sans 'forfait jour' → False."""
        assert is_forfait_jour("cadre au forfait heures") is False
        assert is_forfait_jour("employé") is False


class TestNormalizePlannedCalendarForForfaitJour:
    """Tests de normalize_planned_calendar_for_forfait_jour."""

    def test_non_forfait_jour_returns_unchanged(self):
        """Si pas forfait jour, le calendrier n'est pas modifié."""
        calendrier = [{"jour": 1, "type": "work", "heures_prevues": 8.5}]
        result = normalize_planned_calendar_for_forfait_jour(calendrier, "employé")
        assert result == calendrier

    def test_forfait_jour_normalizes_positive_to_one(self):
        """Forfait jour : heures_prevues > 0 → 1."""
        calendrier = [
            {"jour": 1, "type": "work", "heures_prevues": 8},
            {"jour": 2, "type": "work", "heures_prevues": 0.5},
        ]
        result = normalize_planned_calendar_for_forfait_jour(
            calendrier, "cadre forfait jour"
        )
        assert result[0]["heures_prevues"] == 1
        assert result[1]["heures_prevues"] == 1

    def test_forfait_jour_normalizes_zero_and_none(self):
        """Forfait jour : 0 ou None → 0."""
        calendrier = [
            {"jour": 1, "type": "rest", "heures_prevues": 0},
            {"jour": 2, "type": "weekend"},
        ]
        result = normalize_planned_calendar_for_forfait_jour(
            calendrier, "cadre forfait jour"
        )
        assert result[0]["heures_prevues"] == 0
        assert result[1]["heures_prevues"] == 0

    def test_forfait_jour_preserves_other_keys(self):
        """Les autres clés (jour, type) sont préservées."""
        calendrier = [{"jour": 10, "type": "work", "heures_prevues": 7}]
        result = normalize_planned_calendar_for_forfait_jour(
            calendrier, "cadre forfait jour"
        )
        assert result[0]["jour"] == 10
        assert result[0]["type"] == "work"
        assert result[0]["heures_prevues"] == 1


class TestNormalizeActualHoursForForfaitJour:
    """Tests de normalize_actual_hours_for_forfait_jour."""

    def test_non_forfait_jour_returns_unchanged(self):
        """Si pas forfait jour, le calendrier réel n'est pas modifié."""
        calendrier = [{"jour": 1, "heures_faites": 7.5}]
        result = normalize_actual_hours_for_forfait_jour(calendrier, "employé")
        assert result == calendrier

    def test_forfait_jour_normalizes_heures_faites_positive_to_one(self):
        """Forfait jour : heures_faites > 0 → 1."""
        calendrier = [{"jour": 1, "heures_faites": 6.5}]
        result = normalize_actual_hours_for_forfait_jour(
            calendrier, "cadre forfait jour"
        )
        assert result[0]["heures_faites"] == 1

    def test_forfait_jour_normalizes_heures_faites_zero_and_none(self):
        """Forfait jour : heures_faites 0 ou None → 0."""
        calendrier = [
            {"jour": 1, "heures_faites": 0},
            {"jour": 2},
        ]
        result = normalize_actual_hours_for_forfait_jour(
            calendrier, "cadre forfait jour"
        )
        assert result[0]["heures_faites"] == 0
        assert result[1]["heures_faites"] == 0


# --- Enums ---


class TestDayType:
    """Tests de l'enum DayType."""

    def test_day_type_values(self):
        """Valeurs attendues pour apply-model."""
        assert DayType.WORK == "work"
        assert DayType.TRAVAIL == "travail"
        assert DayType.REST == "rest"
        assert DayType.WEEKEND == "weekend"
        assert DayType.HOLIDAY == "holiday"
        assert DayType.CONGE == "conge"
        assert DayType.FERIE == "ferie"
        assert DayType.ARRET_MALADIE == "arret_maladie"


# --- Exceptions domaine ---


class TestScheduleDomainExceptions:
    """Tests des exceptions du domaine."""

    def test_schedule_not_found_error(self):
        """ScheduleNotFoundError peut être levée avec un message."""
        with pytest.raises(ScheduleNotFoundError, match="Employé non trouvé"):
            raise ScheduleNotFoundError("Employé non trouvé")

    def test_schedule_validation_error(self):
        """ScheduleValidationError peut être levée."""
        with pytest.raises(ScheduleValidationError, match="Mois invalide"):
            raise ScheduleValidationError("Mois invalide")

    def test_schedule_database_error(self):
        """ScheduleDatabaseError peut être levée."""
        with pytest.raises(ScheduleDatabaseError, match="connexion"):
            raise ScheduleDatabaseError("Erreur de connexion à la base")
