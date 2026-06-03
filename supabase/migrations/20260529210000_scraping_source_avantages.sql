-- Source scraping : avantages en nature (repas, titre-restaurant, logement).

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
    'AVANTAGES',
    'Avantages en nature',
    'bareme',
    'Forfaits repas, exonération titre-restaurant et barème logement',
    'payroll_config',
    'avantages_en_nature',
    'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/avantages-en-nature.html',
    '["Avantages.py", "Avantages_LegiSocial.py", "Avantages_AI.py"]'::jsonb,
    'scraping/Avantages/orchestrator.py',
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
