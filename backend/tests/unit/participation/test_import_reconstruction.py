"""Tests unitaires — reconstruction des bulletins participation depuis les saisies.

Fixtures calées sur des cas réels de la base (backtest 2025/2026) : GIRERD
(MBC, 100 % PEE), un cas numéraire+avance, un cas mixte numéraire+PEE+avance.
"""

from __future__ import annotations

from decimal import Decimal

from app.modules.participation.domain.import_reconstruction import (
    reconstruct_bulletins_from_inputs,
)


def _row(employee_id: str, name: str, amount: float, row_id: str) -> dict:
    return {"id": row_id, "employee_id": employee_id, "name": name, "amount": amount}


class TestFullCash:
    def test_numeraire_seul(self):
        rows = [_row("e1", "Participation 2025 — numéraire", 3535.86, "r1")]

        result = reconstruct_bulletins_from_inputs(rows)

        assert len(result) == 1
        b = result[0]
        assert b.employee_id == "e1"
        assert b.choice_type == "full_cash"
        assert b.cash_amount == Decimal("3192.88")
        assert b.pee_amount == Decimal("0.00")
        assert b.net_amount == Decimal("3192.88")
        assert b.advance_amount == Decimal("0")
        assert b.source_input_ids == ["r1"]

    def test_numeraire_avec_avance(self):
        """Cas réel : société MBC, numéraire 3535,86 € + avance -1000 €."""
        rows = [
            _row("e1", "Participation 2025 — numéraire", 3535.86, "r1"),
            _row("e1", "Avance participation 2025 (déjà versée)", -1000.0, "r2"),
        ]

        result = reconstruct_bulletins_from_inputs(rows)

        b = result[0]
        assert b.choice_type == "full_cash"
        assert b.cash_amount == Decimal("2192.88")
        assert b.advance_amount == Decimal("1000")
        assert b.advance_label == "Avance participation 2025 (déjà versée)"
        assert set(b.source_input_ids) == {"r1", "r2"}

    def test_libelle_simple_traite_comme_numeraire(self):
        """Cartol/Lewis : libellé 'Participation 2025' sans suffixe '— numéraire'."""
        rows = [_row("e1", "Participation 2025", 1000.0, "r1")]

        result = reconstruct_bulletins_from_inputs(rows)

        assert result[0].choice_type == "full_cash"


class TestFullPee:
    def test_pee_seul_girerd(self):
        """Cas réel : Fabrice GIRERD, MBC mai 2026, participation 100 % PEE."""
        rows = [_row("e2", "Participation 2025 — PEE", 5331.56, "r1")]

        result = reconstruct_bulletins_from_inputs(rows)

        b = result[0]
        assert b.choice_type == "full_pee"
        assert b.cash_amount == Decimal("0.00")
        assert b.pee_amount == Decimal("4814.40")
        assert b.net_amount == Decimal("4814.40")
        assert b.csg_non_deductible == Decimal("154.62")
        assert b.csg_deductible == Decimal("362.55")


class TestPartialCash:
    def test_numeraire_et_pee_avec_avance(self):
        """Cas réel : numéraire 4429,40 + PEE 559,40 + avance -1000."""
        rows = [
            _row("e3", "Participation 2025 — numéraire", 4429.40, "r1"),
            _row("e3", "Participation 2025 PEE", 559.40, "r2"),
            _row("e3", "Avance participation 2025 (déjà versée)", -1000.0, "r3"),
        ]

        result = reconstruct_bulletins_from_inputs(rows)

        b = result[0]
        assert b.choice_type == "partial_cash"
        assert b.cash_amount == Decimal("2999.75")
        assert b.pee_amount == Decimal("505.14")
        assert b.net_amount == Decimal("3504.89")


class TestExclusions:
    def test_note_de_frais_exclue(self):
        rows = [
            _row("e1", "Participation 2025 — numéraire", 1000.0, "r1"),
            _row("e1", "Remboursement note de frais (participation)", 50.0, "r2"),
        ]

        result = reconstruct_bulletins_from_inputs(rows)

        assert len(result) == 1
        assert result[0].source_input_ids == ["r1"]

    def test_avance_orpheline_ignoree(self):
        """Défensif : aucun cas réel actuel, mais une avance sans numéraire/PEE
        associé ne doit pas créer de bénéficiaire fantôme."""
        rows = [_row("e1", "Avance participation 2025 (déjà versée)", -500.0, "r1")]

        result = reconstruct_bulletins_from_inputs(rows)

        assert result == []

    def test_ligne_non_participation_ignoree(self):
        rows = [_row("e1", "Prime de vacances", 200.0, "r1")]

        result = reconstruct_bulletins_from_inputs(rows)

        assert result == []


class TestMultiEmployees:
    def test_regroupe_par_salarie(self):
        rows = [
            _row("e1", "Participation 2025 — numéraire", 1000.0, "r1"),
            _row("e2", "Participation 2025 — PEE", 500.0, "r2"),
        ]

        result = reconstruct_bulletins_from_inputs(rows)

        assert {b.employee_id for b in result} == {"e1", "e2"}
