-- Variable paie : prime par semaine sans absence.

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
        'per_astreinte_weekend_km',
        'per_astreinte_week_tiered',
        'per_astreinte_weekend_majoration',
        'per_week_without_absence'
    ));
