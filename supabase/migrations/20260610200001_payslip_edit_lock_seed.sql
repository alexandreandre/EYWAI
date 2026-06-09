-- Règle globale : verrouillage de l'édition manuelle des bulletins à partir du J du mois suivant.
INSERT INTO public.payroll_config (
    config_key, config_data, version, is_active, comment, company_id
)
SELECT
    'payslip_edit_lock',
    '{"cutoff_day_of_next_month": 15}'::jsonb,
    1,
    true,
    'Verrouillage édition manuelle bulletins — jour du mois suivant (défaut 15)',
    NULL
WHERE NOT EXISTS (
    SELECT 1 FROM public.payroll_config
    WHERE config_key = 'payslip_edit_lock' AND company_id IS NULL
);
