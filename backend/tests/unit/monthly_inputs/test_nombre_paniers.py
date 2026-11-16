"""Nombre de paniers d'une saisie du mois (guide 1 du 16/11)."""

from __future__ import annotations


def test_saisie_garde_le_nombre_de_paniers():
    """Fenêtre « Nouvelle saisie » : le nombre de paniers arrive au moteur (guide 1, 16/11)."""
    from app.modules.monthly_inputs.schemas.requests import MonthlyInput
    from app.modules.payroll.engine.calcul_frais import valeur_unitaire

    m = MonthlyInput(
        employee_id="00000000-0000-0000-0000-000000000001",
        year=2026,
        month=11,
        name="Panier",
        amount=200,
        is_socially_taxed=False,
        payroll_quantity=20,
        quantity_kind="count",
    )
    dump = m.model_dump(mode="json", exclude_none=True)
    assert dump["payroll_quantity"] == 20 and dump["quantity_kind"] == "count"
    assert (
        valeur_unitaire(dump["amount"], dump["payroll_quantity"], dump["quantity_kind"])
        == 10.0
    )
