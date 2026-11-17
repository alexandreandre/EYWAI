"""Une règle ne garde que les conditions de son type (Lyon, 17/11/2026)."""

from app.modules.payroll_variables.domain.rules import conditions_du_type


def test_un_montant_fixe_perd_les_conditions_d_astreinte_et_garde_les_salaries():
    conditions = {
        "employee_ids": ["e1"],
        "requires_astreinte": True,
        "km_free_threshold_one_way": 10,
        "rate_mode": "coefficient_a",
    }
    assert conditions_du_type("fixed_monthly", conditions) == {"employee_ids": ["e1"]}


def test_une_regle_garde_ses_propres_conditions_et_les_communes():
    conditions = {
        "employee_ids": ["e1"],
        "situation_repas": "sur_lieu_travail",
        "min_heures": 6,
        "shift_type_codes": ["NUIT"],
    }
    assert conditions_du_type("per_worked_day", conditions) == {
        "employee_ids": ["e1"],
        "situation_repas": "sur_lieu_travail",
        "min_heures": 6,
    }


def test_une_cle_partagee_reste_pour_les_deux_types_qui_la_lisent():
    conditions = {"weekend_weekday_numbers": [5, 6], "weekday_rates": {"5": 0.25}}
    assert conditions_du_type("per_astreinte_weekend_km", conditions) == {
        "weekend_weekday_numbers": [5, 6]
    }
    assert conditions_du_type("per_astreinte_weekend_majoration", conditions) == conditions
