"""Tests variables paie — règles domaine."""

from app.modules.payroll_variables.domain.rules import (
    compute_rule_amount,
    employee_matches_conditions,
)


def test_fixed_monthly_productivity_36():
    amount = compute_rule_amount("fixed_monthly", 36.0, None, 1.0)
    assert amount == 36.0


def test_astreinte_two_weeks():
    amount = compute_rule_amount("per_astreinte_week", 50.0, None, 2.0)
    assert amount == 100.0


def test_modulation_payout_below_threshold():
    amount = compute_rule_amount(
        "per_modulation_payout",
        15.0,
        None,
        2.0,
        conditions={"min_balance_hours": 5},
    )
    assert amount == 0.0


def test_modulation_payout_above_threshold():
    amount = compute_rule_amount(
        "per_modulation_payout",
        15.0,
        None,
        8.0,
        conditions={"min_balance_hours": 5},
    )
    assert amount == 120.0


def test_employee_statut_filter():
    emp = {"statut": "Cadre"}
    assert employee_matches_conditions(emp, {"statuts": ["Cadre"]})
    assert not employee_matches_conditions(emp, {"statuts": ["Non-Cadre"]})


def test_employee_ids_filter_matches():
    emp = {"id": "abc-123", "statut": "Non-Cadre"}
    assert employee_matches_conditions(emp, {"employee_ids": ["abc-123"]})


def test_employee_ids_filter_excludes():
    emp = {"id": "abc-123", "statut": "Non-Cadre"}
    assert not employee_matches_conditions(emp, {"employee_ids": ["zzz-999"]})


def test_employee_ids_empty_list_does_not_filter():
    """Une liste vide ne doit cibler personne plutôt que tout le monde."""
    emp = {"id": "abc-123"}
    assert not employee_matches_conditions(emp, {"employee_ids": []})


def test_employee_ids_combines_with_statut():
    emp = {"id": "abc-123", "statut": "Cadre"}
    conditions = {"employee_ids": ["abc-123"], "exclude_statuts": ["Cadre"]}
    assert not employee_matches_conditions(emp, conditions)


def test_transport_rule_type_ignore_le_montant_de_la_regle():
    """Le montant vient de la fiche salarié, pas de la règle : compute_rule_amount
    ne doit pas inventer de valeur pour ce type."""
    assert compute_rule_amount("transport_domicile_travail", 250.0, None, 1.0) == 0.0
