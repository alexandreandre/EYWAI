-- Régime de paie des alternants (apprentis + contrats de professionnalisation).
-- Tous les seuils sont stockés dynamiquement dans payroll_config (config_key = 'alternance'),
-- jamais en dur dans le moteur. Éditable via l'UI « Suivi des taux » et le scraping.
--
-- Régime apprenti déterminé par le 1er jour d'EXÉCUTION du contrat (BOSS) :
--   - exécution < 2025-03-01 : exonération cotis. salariales <= 79 % SMIC, pas de CSG/CRDS
--   - exécution >= 2025-03-01 : exonération <= 50 % SMIC, CSG/CRDS au-delà (abattement 1,75 %)
-- IR exonéré jusqu'au SMIC annuel. Mutuelle / prévoyance / APEC toujours dues.

-- 1) Source scraping (pour maintenance via l'UI et l'orchestrateur de taux)
INSERT INTO public.scraping_sources (
    source_key,
    source_name,
    source_type,
    description,
    target_table,
    target_field,
    primary_url,
    requires_company_context,
    scraping_frequency,
    is_critical,
    is_active
)
VALUES (
    'ALTERNANCE',
    'Régime paie alternants (apprenti / pro)',
    'bareme',
    'Seuils exonération apprenti (50/79 % SMIC), assujettissement CSG/CRDS, exonération IR, codes DSN alternance',
    'payroll_config',
    'alternance',
    'https://boss.gouv.fr/portail/accueil/exonerations-specifiques/apprentis.html',
    false,
    'manual',
    false,
    true
)
ON CONFLICT (source_key) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    source_type = EXCLUDED.source_type,
    description = EXCLUDED.description,
    target_table = EXCLUDED.target_table,
    target_field = EXCLUDED.target_field,
    primary_url = EXCLUDED.primary_url,
    is_critical = EXCLUDED.is_critical,
    is_active = EXCLUDED.is_active,
    updated_at = now();

-- 2) Seed de la configuration alternance (cold start ; non écrasé si déjà présent)
INSERT INTO public.payroll_config (
    config_key, config_data, version, is_active, comment, company_id
)
SELECT
    'alternance',
    '{
        "apprenti": {
            "regimes": [
                {
                    "date_execution_min": null,
                    "date_execution_max": "2025-02-28",
                    "plafond_exoneration_pct_smic": 0.79,
                    "csg_crds_assujettie_au_dela_plafond": false,
                    "libelle": "Apprenti - exécution avant le 01/03/2025"
                },
                {
                    "date_execution_min": "2025-03-01",
                    "date_execution_max": null,
                    "plafond_exoneration_pct_smic": 0.50,
                    "csg_crds_assujettie_au_dela_plafond": true,
                    "libelle": "Apprenti - exécution à partir du 01/03/2025"
                }
            ],
            "abattement_csg_frais_pro": 0.0175,
            "cotisations_exclues_exoneration": [
                "mutuelle",
                "prevoyance_cadre",
                "prevoyance_non_cadre",
                "apec"
            ],
            "exoneration_ir": {
                "actif": true,
                "plafond_annuel_pct_smic": 1.0
            }
        },
        "professionnalisation": {
            "exonerations_patronales": []
        },
        "dsn": {
            "codes_dispositif_politique_publique": {
                "Apprentissage": "64",
                "Contrat de professionnalisation": "61"
            }
        }
    }'::jsonb,
    1, true, 'Seed régime alternance (apprenti/pro) — seuils LFSS 2025', NULL
WHERE NOT EXISTS (
    SELECT 1 FROM public.payroll_config
    WHERE config_key = 'alternance' AND company_id IS NULL
);
