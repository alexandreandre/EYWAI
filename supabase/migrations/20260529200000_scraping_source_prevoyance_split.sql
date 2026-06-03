-- Séparer la prévoyance en deux sources (mise à jour indépendante par carte).

UPDATE public.scraping_sources
SET is_active = false, updated_at = now()
WHERE source_key = 'PREVOYANCE';

INSERT INTO public.scraping_sources (
    source_key,
    source_name,
    source_type,
    description,
    target_table,
    target_field,
    primary_url,
    available_scrapers,
    orchestrator_path,
    requires_company_context,
    scraping_frequency,
    is_critical,
    is_active
)
VALUES (
    'PREVOYANCE_CADRE',
    'Prévoyance cadre — minimum légal ANI (1,50 % T1)',
    'cotisation',
    'Minimum patronal obligatoire pour les cadres (ANI, tranche 1)',
    'payroll_config',
    'cotisations.prevoyance_cadre',
    'https://www.service-public.fr/professionnels-entreprises/vosdroits/F33666',
    '["prevoyance.py"]'::jsonb,
    'scraping/prevoyance/orchestrator_cadre.py',
    false,
    'manual',
    false,
    true
),
(
    'PREVOYANCE_NON_CADRE',
    'Prévoyance non-cadre — barème de référence',
    'cotisation',
    'Contrôle du barème de référence (taux selon convention collective)',
    'payroll_config',
    'cotisations.prevoyance_non_cadre',
    'https://www.service-public.fr/professionnels-entreprises/vosdroits/F33666',
    '["prevoyance.py"]'::jsonb,
    'scraping/prevoyance/orchestrator_non_cadre.py',
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
    available_scrapers = EXCLUDED.available_scrapers,
    orchestrator_path = EXCLUDED.orchestrator_path,
    is_critical = EXCLUDED.is_critical,
    is_active = EXCLUDED.is_active,
    updated_at = now();
