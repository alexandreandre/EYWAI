"""
Tests unitaires du domaine monthly_inputs : entités, value objects et règles métier.

Aucune dépendance DB ni HTTP. Couvre :
- MonthlyInputEntity (domain/entities.py)
- Period (domain/value_objects.py)
- is_valid_period (domain/rules.py)
"""
from datetime import datetime
from uuid import uuid4

import pytest

from app.modules.monthly_inputs.domain.entities import MonthlyInputEntity
from app.modules.monthly_inputs.domain.rules import is_valid_period
from app.modules.monthly_inputs.domain.value_objects import Period


# --- Entités ---


class TestMonthlyInputEntity:
    """Tests de l'entité MonthlyInputEntity."""

    def test_entity_creation_minimal(self):
        """Création avec champs obligatoires uniquement."""
        emp_id = uuid4()
        entity = MonthlyInputEntity(
            employee_id=emp_id,
            year=2025,
            month=3,
            name="Prime exceptionnelle",
            amount=500.0,
        )
        assert entity.employee_id == emp_id
        assert entity.year == 2025
        assert entity.month == 3
        assert entity.name == "Prime exceptionnelle"
        assert entity.amount == 500.0
        assert entity.description is None
        assert entity.is_socially_taxed is True
        assert entity.is_taxable is True
        assert entity.id is None
        assert entity.created_at is None
        assert entity.updated_at is None

    def test_entity_creation_full(self):
        """Création avec tous les champs optionnels."""
        eid = uuid4()
        emp_id = uuid4()
        created = datetime(2025, 3, 1, 10, 0, 0)
        updated = datetime(2025, 3, 2, 14, 0, 0)
        entity = MonthlyInputEntity(
            id=eid,
            employee_id=emp_id,
            year=2025,
            month=3,
            name="Acompte",
            amount=200.0,
            description="Acompte sur prime mars",
            is_socially_taxed=False,
            is_taxable=True,
            created_at=created,
            updated_at=updated,
        )
        assert entity.id == eid
        assert entity.employee_id == emp_id
        assert entity.description == "Acompte sur prime mars"
        assert entity.is_socially_taxed is False
        assert entity.is_taxable is True
        assert entity.created_at == created
        assert entity.updated_at == updated

    def test_entity_defaults_taxable(self):
        """Valeurs par défaut : is_socially_taxed et is_taxable à True."""
        entity = MonthlyInputEntity(
            employee_id=uuid4(),
            year=2025,
            month=1,
            name="Prime",
            amount=100.0,
        )
        assert entity.is_socially_taxed is True
        assert entity.is_taxable is True


# --- Value objects ---


class TestPeriod:
    """Tests du value object Period."""

    def test_period_creation(self):
        """Période (année, mois) pour filtrer les saisies."""
        period = Period(year=2025, month=6)
        assert period.year == 2025
        assert period.month == 6

    def test_period_frozen(self):
        """Period est immutable (frozen dataclass)."""
        from dataclasses import FrozenInstanceError

        period = Period(year=2024, month=12)
        with pytest.raises(FrozenInstanceError):
            period.month = 1  # type: ignore[misc]

    def test_period_boundaries(self):
        """Mois 1 et 12 sont valides."""
        p1 = Period(year=2025, month=1)
        p12 = Period(year=2025, month=12)
        assert p1.month == 1
        assert p12.month == 12


# --- Règles métier : is_valid_period ---


class TestIsValidPeriod:
    """Règle : période (année, mois) valide pour une saisie mensuelle."""

    def test_valid_period_returns_true(self):
        """Année > 0 et mois entre 1 et 12 → True."""
        assert is_valid_period(2025, 1) is True
        assert is_valid_period(2025, 6) is True
        assert is_valid_period(2025, 12) is True
        assert is_valid_period(1, 1) is True

    @pytest.mark.parametrize(
        "year,month",
        [
            (2025, 0),
            (2025, 13),
            (2025, -1),
            (0, 6),
            (-1, 6),
        ],
    )
    def test_invalid_month_or_year_returns_false(self, year: int, month: int):
        """Mois hors 1-12 ou année <= 0 → False."""
        assert is_valid_period(year, month) is False

    def test_non_integer_returns_false(self):
        """Types non int (float, str) ne sont pas valides (isinstance check)."""
        assert is_valid_period(2025.0, 6) is False  # type: ignore[arg-type]
        assert is_valid_period(2025, 6.0) is False  # type: ignore[arg-type]
        assert is_valid_period("2025", 6) is False  # type: ignore[arg-type]
        assert is_valid_period(2025, "6") is False  # type: ignore[arg-type]
