"""
Tests unitaires du domaine bonus_types : entités, value objects, enums et règles.

Sans DB, sans HTTP. Couvre toutes les entités et règles du domain/.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from app.modules.bonus_types.domain.entities import BonusType
from app.modules.bonus_types.domain.enums import BonusTypeKind
from app.modules.bonus_types.domain.value_objects import BonusAmountComputation
from app.modules.bonus_types.domain.rules import (
    validate_seuil_heures_for_kind,
    compute_bonus_amount,
)


class TestBonusTypeKind:
    """Enum BonusTypeKind."""

    def test_montant_fixe_value(self):
        assert BonusTypeKind.MONTANT_FIXE.value == "montant_fixe"

    def test_selon_heures_value(self):
        assert BonusTypeKind.SELON_HEURES.value == "selon_heures"

    def test_from_string(self):
        assert BonusTypeKind("montant_fixe") == BonusTypeKind.MONTANT_FIXE
        assert BonusTypeKind("selon_heures") == BonusTypeKind.SELON_HEURES


class TestBonusTypeEntity:
    """Entité domaine BonusType."""

    def test_entity_creation_with_required_fields(self):
        company_id = uuid4()
        bonus = BonusType(
            id=None,
            company_id=company_id,
            libelle="Prime fixe",
            type=BonusTypeKind.MONTANT_FIXE,
            montant=100.0,
            seuil_heures=None,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
        )
        assert bonus.id is None
        assert bonus.company_id == company_id
        assert bonus.libelle == "Prime fixe"
        assert bonus.type == BonusTypeKind.MONTANT_FIXE
        assert bonus.montant == 100.0
        assert bonus.seuil_heures is None
        assert bonus.soumise_a_cotisations is True
        assert bonus.soumise_a_impot is True
        assert bonus.prompt_ia is None
        assert bonus.created_at is None
        assert bonus.updated_at is None
        assert bonus.created_by is None

    def test_entity_with_selon_heures_and_seuil(self):
        company_id = uuid4()
        bonus_id = uuid4()
        now = datetime.now()
        bonus = BonusType(
            id=bonus_id,
            company_id=company_id,
            libelle="Prime heures",
            type=BonusTypeKind.SELON_HEURES,
            montant=50.0,
            seuil_heures=151.67,
            soumise_a_cotisations=True,
            soumise_a_impot=False,
            prompt_ia="Prime si heures complètes",
            created_at=now,
            updated_at=now,
            created_by=company_id,
        )
        assert bonus.id == bonus_id
        assert bonus.type == BonusTypeKind.SELON_HEURES
        assert bonus.seuil_heures == 151.67
        assert bonus.prompt_ia == "Prime si heures complètes"
        assert bonus.created_at == now


class TestBonusAmountComputation:
    """Value object BonusAmountComputation."""

    def test_montant_fixe_computation_shape(self):
        comp = BonusAmountComputation(amount=200.0)
        assert comp.amount == 200.0
        assert comp.total_hours is None
        assert comp.seuil is None
        assert comp.condition_met is None

    def test_selon_heures_computation_shape(self):
        comp = BonusAmountComputation(
            amount=100.0,
            total_hours=160.0,
            seuil=151.67,
            condition_met=True,
        )
        assert comp.amount == 100.0
        assert comp.total_hours == 160.0
        assert comp.seuil == 151.67
        assert comp.condition_met is True

    def test_frozen(self):
        comp = BonusAmountComputation(amount=10.0)
        with pytest.raises(Exception):  # FrozenInstanceError
            comp.amount = 20.0


class TestValidateSeuilHeuresForKind:
    """Règle validate_seuil_heures_for_kind."""

    def test_selon_heures_without_seuil_raises(self):
        with pytest.raises(ValueError) as exc_info:
            validate_seuil_heures_for_kind(BonusTypeKind.SELON_HEURES, None)
        assert "seuil_heures est requis" in str(exc_info.value)
        assert "selon_heures" in str(exc_info.value)

    def test_selon_heures_with_seuil_ok(self):
        validate_seuil_heures_for_kind(BonusTypeKind.SELON_HEURES, 151.67)  # no raise

    def test_montant_fixe_with_seuil_raises(self):
        with pytest.raises(ValueError) as exc_info:
            validate_seuil_heures_for_kind(BonusTypeKind.MONTANT_FIXE, 100.0)
        assert "seuil_heures ne doit être renseigné" in str(exc_info.value)
        assert "selon_heures" in str(exc_info.value)

    def test_montant_fixe_without_seuil_ok(self):
        validate_seuil_heures_for_kind(BonusTypeKind.MONTANT_FIXE, None)  # no raise


class TestComputeBonusAmount:
    """Règle compute_bonus_amount (logique pure)."""

    def test_montant_fixe_returns_fixed_amount(self):
        company_id = uuid4()
        bonus = BonusType(
            id=None,
            company_id=company_id,
            libelle="Prime fixe",
            type=BonusTypeKind.MONTANT_FIXE,
            montant=250.0,
            seuil_heures=None,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
        )
        result = compute_bonus_amount(bonus, 0.0)
        assert result.amount == 250.0
        assert result.total_hours is None
        assert result.seuil is None
        assert result.condition_met is None

    def test_montant_fixe_ignores_total_hours(self):
        company_id = uuid4()
        bonus = BonusType(
            id=None,
            company_id=company_id,
            libelle="Prime fixe",
            type=BonusTypeKind.MONTANT_FIXE,
            montant=100.0,
            seuil_heures=None,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
        )
        result = compute_bonus_amount(bonus, 200.0)
        assert result.amount == 100.0

    def test_selon_heures_above_threshold_returns_montant(self):
        company_id = uuid4()
        bonus = BonusType(
            id=None,
            company_id=company_id,
            libelle="Prime heures",
            type=BonusTypeKind.SELON_HEURES,
            montant=80.0,
            seuil_heures=151.67,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
        )
        result = compute_bonus_amount(bonus, 160.0)
        assert result.amount == 80.0
        assert result.total_hours == 160.0
        assert result.seuil == 151.67
        assert result.condition_met is True

    def test_selon_heures_below_threshold_returns_zero(self):
        company_id = uuid4()
        bonus = BonusType(
            id=None,
            company_id=company_id,
            libelle="Prime heures",
            type=BonusTypeKind.SELON_HEURES,
            montant=80.0,
            seuil_heures=151.67,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
        )
        result = compute_bonus_amount(bonus, 140.0)
        assert result.amount == 0.0
        assert result.total_hours == 140.0
        assert result.seuil == 151.67
        assert result.condition_met is False

    def test_selon_heures_exactly_at_threshold_returns_montant(self):
        company_id = uuid4()
        bonus = BonusType(
            id=None,
            company_id=company_id,
            libelle="Prime heures",
            type=BonusTypeKind.SELON_HEURES,
            montant=50.0,
            seuil_heures=151.67,
            soumise_a_cotisations=True,
            soumise_a_impot=True,
            prompt_ia=None,
        )
        result = compute_bonus_amount(bonus, 151.67)
        assert result.amount == 50.0
        assert result.condition_met is True
