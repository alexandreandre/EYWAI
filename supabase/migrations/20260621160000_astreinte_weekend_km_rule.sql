-- Recette RH : créer un company_bonus_type « Indemnité km astreinte » (non soumis),
-- puis une règle code astreinte_km / per_astreinte_weekend_km (voir tests/recette_astreinte_km.py).
ALTER TABLE public.company_payroll_variable_rules
    DROP CONSTRAINT IF EXISTS company_payroll_variable_rules_rule_type_check;

ALTER TABLE public.company_payroll_variable_rules
    ADD CONSTRAINT company_payroll_variable_rules_rule_type_check
    CHECK (rule_type IN (
        'fixed_monthly',
        'per_astreinte_week',
        'per_shift_type',
        'per_modulation_payout',
        'per_night_hour',
        'per_astreinte_weekend_km'
    ));
