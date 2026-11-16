-- Variables de paie : règle « Par jour travaillé » (jours lus dans le calendrier du salarié).
-- Ajoute aussi « transport_domicile_travail », accepté par l'API mais refusé par la base.
alter table public.company_payroll_variable_rules
  drop constraint if exists company_payroll_variable_rules_rule_type_check;
alter table public.company_payroll_variable_rules
  add constraint company_payroll_variable_rules_rule_type_check
  check (rule_type = any (array[
    'fixed_monthly', 'per_astreinte_week', 'per_shift_type', 'per_worked_day',
    'per_modulation_payout', 'per_night_hour', 'per_astreinte_weekend_km',
    'per_astreinte_week_tiered', 'per_astreinte_weekend_majoration',
    'per_week_without_absence', 'transport_domicile_travail'
  ]::text[]));
