-- Régime stage (gratification) et CDD (prime de précarité).
-- Seuils dynamiques dans payroll_config — jamais en dur dans le moteur.

INSERT INTO public.payroll_config (
    config_key, config_data, version, is_active, comment, company_id
)
SELECT
    'stage',
    '{
        "actif": true,
        "pct_plafond_horaire_ss": 0.15,
        "libelle": "Exonération gratification de stage (15 % plafond horaire SS)"
    }'::jsonb,
    1, true, 'Seed régime stage — gratification exonérée sous 15 % PSS horaire', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM public.payroll_config
    WHERE config_key = 'stage' AND company_id IS NULL
);

INSERT INTO public.payroll_config (
    config_key, config_data, version, is_active, comment, company_id
)
SELECT
    'cdd',
    '{
        "precarite": {
            "actif": true,
            "taux": 0.10,
            "libelle": "Prime de précarité CDD (10 % du brut cumulé du contrat)"
        },
        "indemnite_conges": {
            "actif": true,
            "taux": 0.10,
            "libelle": "Indemnité compensatrice de congés payés CDD (1/10e)"
        }
    }'::jsonb,
    1, true, 'Seed prime de précarité + ICCP CDD', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM public.payroll_config
    WHERE config_key = 'cdd' AND company_id IS NULL
);
