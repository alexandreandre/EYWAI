-- Seed payroll_config pour la CSG/CRDS sur IJSS subrogées (arrêt maladie).
-- Taux des revenus de remplacement : 3,8 % déductible + 2,9 % non déductible
-- (CSG 2,4 % + CRDS 0,5 %). Idempotent.

INSERT INTO public.payroll_config (
    config_key, config_data, version, is_active, comment, company_id
)
SELECT
    'maladie',
    '{
        "csg_ijss": {
            "taux_deductible": 0.038,
            "taux_non_deductible": 0.029,
            "libelle": "CSG/CRDS sur IJSS subrogées (revenus de remplacement)"
        }
    }'::jsonb,
    1, true, 'Seed CSG/CRDS sur IJSS subrogées', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM public.payroll_config
    WHERE config_key = 'maladie' AND company_id IS NULL
);
