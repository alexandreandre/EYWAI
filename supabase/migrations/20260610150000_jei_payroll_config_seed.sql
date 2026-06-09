-- Barème national JEI (Jeune Entreprise Innovante) — exonérations cotisations patronales.
INSERT INTO public.payroll_config (
    config_key, config_data, version, is_active, comment, company_id
)
SELECT
    'jei',
    '{
        "actif": true,
        "facteur_smic_plafond": 4.5,
        "facteur_pass_plafond_annuel": 5,
        "duree_annees": 7,
        "cotisations_exonerees_patronales": [
            "securite_sociale_maladie",
            "retraite_secu_plafond",
            "retraite_secu_deplafond",
            "allocations_familiales"
        ]
    }'::jsonb,
    1,
    true,
    'Exonération JEI — plafonds 4,5 SMIC / 5 PASS, cotisations patronales éligibles',
    NULL
WHERE NOT EXISTS (
    SELECT 1 FROM public.payroll_config
    WHERE config_key = 'jei' AND company_id IS NULL
);
