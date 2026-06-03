-- Source scraping pour les plafonds IJSS (ij_plafonds / orchestrateur IJmaladie).

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
    'IJ_MALADIE',
    'Plafonds indemnités journalières (IJSS)',
    'plafond',
    'Plafonds IJSS : maladie, maternité/paternité, AT/MP',
    'payroll_config',
    'ij_plafonds.plafonds_indemnites_journalieres',
    'https://www.ameli.fr/entreprise/vos-salaries/montants-reference/indemnites-journalieres-montants-maximum',
    '["IJmaladie.py", "IJmaladie_LegiSocial.py", "IJmaladie_AI.py"]'::jsonb,
    'scraping/IJmaladie/orchestrator.py',
    false,
    'manual',
    true,
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
