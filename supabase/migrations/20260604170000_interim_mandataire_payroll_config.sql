-- Seeds payroll_config pour les régimes intérim et mandataire social.
-- Idempotent : n'insère que si la clé globale (company_id NULL) n'existe pas.
-- Aucun taux en dur côté moteur : tout vient de payroll_config.

-- Intérim : indemnité de fin de mission (IFM) + indemnité compensatrice CP (ICCP).
INSERT INTO public.payroll_config (
    config_key, config_data, version, is_active, comment, company_id
)
SELECT
    'interim',
    '{
        "ifm": {
            "actif": true,
            "taux": 0.10,
            "libelle": "Indemnité de fin de mission (10 % du brut de la mission)"
        },
        "indemnite_conges": {
            "actif": true,
            "taux": 0.10,
            "libelle": "Indemnité compensatrice de congés payés intérim (1/10e)"
        }
    }'::jsonb,
    1, true, 'Seed régime intérim — IFM + ICCP', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM public.payroll_config
    WHERE config_key = 'interim' AND company_id IS NULL
);

-- Mandataire social assimilé salarié : exclusions d'assiette (chômage / AGS).
INSERT INTO public.payroll_config (
    config_key, config_data, version, is_active, comment, company_id
)
SELECT
    'mandataire',
    '{
        "cotisations_exclues": ["assurance_chomage", "ags", "chomage", "apec"],
        "libelle": "Mandataire social — exclusion assurance chômage / AGS"
    }'::jsonb,
    1, true, 'Seed régime mandataire social', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM public.payroll_config
    WHERE config_key = 'mandataire' AND company_id IS NULL
);
