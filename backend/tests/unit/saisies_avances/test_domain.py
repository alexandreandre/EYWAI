"""
Tests du domaine saisies_avances : règles métier, constantes et types.

Sans DB, sans HTTP. Couvre domain/rules.py et domain/enums.py.
Les entités et value_objects sont des placeholders (pas de logique à tester).
"""
from datetime import date
from decimal import Decimal

import pytest

from app.modules.saisies_avances.domain import rules
from app.modules.saisies_avances.domain.enums import (
    AUTO_APPROVAL_THRESHOLD_EUR,
    MAX_ADVANCE_DAYS,
)


# --- Constantes (enums) ---


class TestDomainEnums:
    """Constantes et types du domaine."""

    def test_auto_approval_threshold_eur(self):
        assert AUTO_APPROVAL_THRESHOLD_EUR == 100

    def test_max_advance_days(self):
        assert MAX_ADVANCE_DAYS == 10


# --- calculate_seizable_amount ---


class TestCalculateSeizableAmount:
    """Règle : quotité saisissable selon barème français."""

    def test_salaire_inferieur_500_euro_zero_saisissable(self):
        assert rules.calculate_seizable_amount(Decimal("400")) == Decimal("0")
        assert rules.calculate_seizable_amount(Decimal("500")) == Decimal("0")

    def test_tranche_500_1000_dix_pourcent(self):
        # (600 - 500) * 0.10 = 10
        assert rules.calculate_seizable_amount(Decimal("600")) == Decimal("10")
        # (1000 - 500) * 0.10 = 50
        assert rules.calculate_seizable_amount(Decimal("1000")) == Decimal("50")

    def test_tranche_1000_2000_vingt_pourcent(self):
        # 50 + (1500 - 1000) * 0.20 = 50 + 100 = 150
        assert rules.calculate_seizable_amount(Decimal("1500")) == Decimal("150")
        # 50 + (2000 - 1000) * 0.20 = 250
        assert rules.calculate_seizable_amount(Decimal("2000")) == Decimal("250")

    def test_tranche_superieure_2000_trente_pourcent(self):
        # 250 + (3000 - 2000) * 0.30 = 550
        assert rules.calculate_seizable_amount(Decimal("3000")) == Decimal("550")

    def test_minimum_untouchable_un_vingtieme(self):
        # Salaire 2000 : max saisissable = 2000 - 2000/20 = 1900
        # Barème donne 250, donc min(250, 1900) = 250
        assert rules.calculate_seizable_amount(Decimal("2000")) == Decimal("250")
        # Salaire 500 : barème 0, minimum à conserver 25, donc 0
        assert rules.calculate_seizable_amount(Decimal("500")) == Decimal("0")

    def test_majoration_par_charge(self):
        # 400€ + 1 charge (104) = 504 → tranche 2 → (504-500)*0.10 = 0.4
        # max_seizable = 400 - 20 = 380, donc min(0.4, 380) = 0.4
        result = rules.calculate_seizable_amount(Decimal("400"), dependents_count=1)
        assert result == Decimal("0.4")
        # 0 charge : 400 reste <= 500 → 0
        assert rules.calculate_seizable_amount(Decimal("400"), dependents_count=0) == Decimal("0")


# --- apply_priority_order ---


class TestApplyPriorityOrder:
    """Tri des saisies par priorité puis date de début."""

    def test_tri_par_priority_puis_start_date(self):
        seizures = [
            {"id": "1", "priority": 2, "start_date": date(2024, 6, 1)},
            {"id": "2", "priority": 1, "start_date": date(2024, 3, 1)},
            {"id": "3", "priority": 1, "start_date": date(2024, 1, 1)},
        ]
        ordered = rules.apply_priority_order(seizures)
        assert [s["id"] for s in ordered] == ["3", "2", "1"]

    def test_priority_par_defaut_4(self):
        seizures = [
            {"id": "a"},
            {"id": "b", "priority": 4},
        ]
        ordered = rules.apply_priority_order(seizures)
        assert len(ordered) == 2


# --- calculate_seizure_deduction ---


class TestCalculateSeizureDeduction:
    """Montant à prélever par saisie selon mode (fixe, pourcentage, barème_legal)."""

    def test_mode_fixe(self):
        seizure = {"calculation_mode": "fixe", "amount": 100}
        # plafonné par seizable_amount
        assert rules.calculate_seizure_deduction(
            seizure, Decimal("2000"), Decimal("500"), 0
        ) == Decimal("100")
        assert rules.calculate_seizure_deduction(
            seizure, Decimal("2000"), Decimal("50"), 0
        ) == Decimal("50")

    def test_mode_pourcentage(self):
        seizure = {"calculation_mode": "pourcentage", "percentage": 10}
        # 2000 * 10% = 200, plafonné par seizable_amount
        assert rules.calculate_seizure_deduction(
            seizure, Decimal("2000"), Decimal("500"), 0
        ) == Decimal("200")
        assert rules.calculate_seizure_deduction(
            seizure, Decimal("2000"), Decimal("100"), 0
        ) == Decimal("100")

    def test_mode_breme_legal_avec_amount(self):
        seizure = {"calculation_mode": "barème_legal", "amount": 80}
        assert rules.calculate_seizure_deduction(
            seizure, Decimal("2000"), Decimal("500"), 0
        ) == Decimal("80")

    def test_mode_breme_legal_sans_amount_retourne_seizable(self):
        seizure = {"calculation_mode": "barème_legal"}
        assert rules.calculate_seizure_deduction(
            seizure, Decimal("2000"), Decimal("250"), 0
        ) == Decimal("250")


# --- compute_advance_available_from_figures ---


class TestComputeAdvanceAvailableFromFigures:
    """Montant disponible pour une avance à partir des chiffres."""

    def test_disponible_plafonne_par_jours_et_outstanding(self):
        daily = Decimal("100")
        days_worked = Decimal("15")
        total_outstanding = Decimal("500")
        available, max_cap = rules.compute_advance_available_from_figures(
            daily, days_worked, total_outstanding, max_advance_days=10
        )
        # gross_available = 100 * 15 = 1500, available = 1500 - 500 = 1000
        # max_advance = 100 * 10 = 1000
        assert available == Decimal("1000")
        assert max_cap == Decimal("1000")

    def test_disponible_zero_si_outstanding_superieur(self):
        daily = Decimal("100")
        days_worked = Decimal("5")
        total_outstanding = Decimal("1000")
        available, _ = rules.compute_advance_available_from_figures(
            daily, days_worked, total_outstanding, max_advance_days=10
        )
        assert available == Decimal("0")


# --- initial_advance_status ---


class TestInitialAdvanceStatus:
    """Statut initial d'une demande d'avance (employé vs RH)."""

    def test_employe_request_toujours_pending(self):
        assert rules.initial_advance_status(True, Decimal("50"), Decimal("100")) == "pending"
        assert rules.initial_advance_status(True, Decimal("200"), Decimal("100")) == "pending"

    def test_rh_sous_seuil_approved(self):
        assert rules.initial_advance_status(
            False, Decimal("80"), Decimal("100")
        ) == "approved"

    def test_rh_au_dessus_seuil_pending(self):
        assert rules.initial_advance_status(
            False, Decimal("150"), Decimal("100")
        ) == "pending"


# --- remaining_to_pay_value ---


class TestRemainingToPayValue:
    """Montant restant à verser (affichage)."""

    def test_restant_positif(self):
        assert rules.remaining_to_pay_value(Decimal("500"), Decimal("200")) == 300.0

    def test_deja_integralement_paye_zero(self):
        assert rules.remaining_to_pay_value(Decimal("500"), Decimal("500")) == 0.0
        assert rules.remaining_to_pay_value(Decimal("500"), Decimal("600")) == 0.0

    def test_approved_zero_retourne_zero(self):
        assert rules.remaining_to_pay_value(Decimal("0"), Decimal("0")) == 0.0
