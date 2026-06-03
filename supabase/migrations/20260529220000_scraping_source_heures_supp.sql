-- Source scraping : heures supplémentaires (majorations, réduction salariale, déduction patronale).

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
    'HEURES_SUPP',
    'Heures supplémentaires',
    'bareme',
    'Majorations, réduction salariale et déduction patronale sur les heures supplémentaires',
    'payroll_config',
    'heures_supp',
    'https://travail-emploi.gouv.fr/droit-du-travail/temps-de-travail/article/les-heures-supplementaires',
    '["heuressupp.py"]'::jsonb,
    'scraping/heuressupp/orchestrator.py',
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
